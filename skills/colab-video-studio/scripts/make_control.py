#!/usr/bin/env python3
"""Render authored OpenPose-style 18-joint trajectories into a control video.

Coordinates are normalized image coordinates, not a motion-capture solution.
Use upstream pose extraction for footage. Preview every authored control clip.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile


COLORS=[(255,0,0),(255,85,0),(255,170,0),(255,255,0),(170,255,0),(85,255,0),
        (0,255,0),(0,255,85),(0,255,170),(0,255,255),(0,170,255),(0,85,255),
        (0,0,255),(85,0,255),(170,0,255),(255,0,255),(255,0,170),(255,0,85)]
LIMBS=[(1,2),(1,5),(2,3),(3,4),(5,6),(6,7),(1,8),(8,9),(9,10),
       (1,11),(11,12),(12,13),(1,0),(0,14),(14,16),(0,15),(15,17)]


def validate(spec):
    width,height,fps=spec["width"],spec["height"],spec["fps"]
    if any(not isinstance(v,int) or v < 1 for v in (width,height,fps)) or width%2 or height%2:
        raise ValueError("Even canvas and positive integer fps required")
    keys=spec["keyframes"]
    times=[k["seconds"] for k in keys]
    if len(keys)<2 or times[0]!=0 or times[-1]!=spec["duration_seconds"] or any(b<=a for a,b in zip(times,times[1:])):
        raise ValueError("Keyframes must start0, end at duration, and increase strictly")
    for key in keys:
        if len(key["joints"])!=18:
            raise ValueError("Use18 OpenPose body joints; missing joints are null")
        for point in key["joints"]:
            if point is not None and (len(point)!=2 or any(not isinstance(v,(int,float)) or not 0<=v<=1 for v in point)):
                raise ValueError("Joint coordinates must lie in0..1")
    return spec


def joints_at(spec,seconds):
    keys=spec["keyframes"]
    index=next((i for i in range(len(keys)-1) if keys[i]["seconds"]<=seconds<=keys[i+1]["seconds"]),len(keys)-2)
    a,b=keys[index:index+2]
    mix=(seconds-a["seconds"])/(b["seconds"]-a["seconds"])
    return [None if left is None or right is None else [left[j]*(1-mix)+right[j]*mix for j in (0,1)]
            for left,right in zip(a["joints"],b["joints"])]


def raster(spec,joints):
    width,height=spec["width"],spec["height"]
    pixels=bytearray(width*height*3)
    points=[None if p is None else (round(p[0]*(width-1)),round(p[1]*(height-1))) for p in joints]
    def disk(x,y,color,radius=3):
        for yy in range(max(0,y-radius),min(height,y+radius+1)):
            for xx in range(max(0,x-radius),min(width,x+radius+1)):
                if (xx-x)**2+(yy-y)**2<=radius**2:
                    offset=(yy*width+xx)*3
                    pixels[offset:offset+3]=bytes(color)
    for i,(start,end) in enumerate(LIMBS):
        if points[start] is None or points[end] is None:
            continue
        a,b=points[start],points[end]
        steps=max(abs(b[0]-a[0]),abs(b[1]-a[1]),1)
        for k in range(steps+1):
            disk(round(a[0]+(b[0]-a[0])*k/steps),round(a[1]+(b[1]-a[1])*k/steps),COLORS[i],2)
    for point,color in zip(points,COLORS):
        if point:
            disk(*point,color,4)
    return f"P6\n{width} {height}\n255\n".encode()+pixels


def render(spec,output):
    validate(spec)
    output=Path(output)
    if output.exists():
        raise ValueError("Control output already exists; use a new revision")
    output.parent.mkdir(parents=True,exist_ok=True)
    count=round(spec["duration_seconds"]*spec["fps"])
    with tempfile.TemporaryDirectory(prefix="pose-control-") as root:
        for n in range(count):
            Path(root,f"{n:06d}.ppm").write_bytes(raster(spec,joints_at(spec,n/spec["fps"])))
        subprocess.run(["ffmpeg","-v","error","-framerate",str(spec["fps"]),"-i",str(Path(root,"%06d.ppm")),
            "-c:v","libx264","-crf","12","-pix_fmt","yuv420p",str(output)],check=True)
    return output


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args()
    render(json.loads(args.spec.read_text()),args.output)
    print(args.output)

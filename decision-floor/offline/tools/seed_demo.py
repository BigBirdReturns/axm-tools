"""Seed one isolated demonstration workspace, never the customer folder."""
import argparse
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import prepare_project,scan

PACKAGE=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--project',default='local_demo');p.add_argument('--scenario',choices=('missed','closed'),default='missed');args=p.parse_args()
    dst=Path(args.project).resolve()
    if dst.name=='local_customer':p.error('Synthetic demonstration must never populate local_customer')
    project=prepare_project(dst)
    incoming=project/'incoming'
    if any(incoming.iterdir()):p.error('Demonstration workspace is not empty; use a fresh folder to avoid mixing records')
    shutil.copytree(PACKAGE/'sample_inputs'/args.scenario,incoming,dirs_exist_ok=True)
    print(scan(project))

if __name__=='__main__':main()

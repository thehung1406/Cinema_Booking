"""Record hardware/framework facts without dumping environment variables or credentials."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    import torch
    import transformers
    report = dict(captured_at=datetime.now(timezone.utc).isoformat(), os=platform.platform(),
        python=platform.python_version(), torch=torch.__version__, transformers=transformers.__version__,
        cuda_available=torch.cuda.is_available(), cuda_runtime=torch.version.cuda,
        torch_threads=torch.get_num_threads(), code_commit=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip())
    if torch.cuda.is_available():
        props=torch.cuda.get_device_properties(0)
        report["gpu"]=dict(name=props.name,total_memory_bytes=props.total_memory,
            compute_capability=f"{props.major}.{props.minor}")
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()

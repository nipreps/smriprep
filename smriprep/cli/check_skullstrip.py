import sys
import argparse
import smriprep
from smriprep.utils.images import is_skull_stripped


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    parser = argparse.ArgumentParser(
        description="Test whether an image is skull-stripped according to current heuristic")
    parser.add_argument("--version", action="version", version=smriprep.__version__)
    parser.add_argument("image", nargs="+", help="Images to test")
    parser.add_argument("--empty-sides", type=int, metavar="N", default=4,
                        help="Minimum number of empty sides (1-6) to consider image "
                        "skull-stripped")
    parser.add_argument("--threshold", type=float, metavar="THRESH", default=10.0,
                        help="Maximum sum of voxels in side to consider 'empty'")

    opts = parser.parse_args(args)
    for image in opts.image:
        masked = "MASKED" if is_skull_stripped(image, opts.empty_sides, opts.threshold) else "ORIG"
        print(f"{image}: {masked}")


if __name__ == "__main__":
    main()

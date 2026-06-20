#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 <standard|staticx> <x86_64|aarch64>" >&2
    exit 2
}

if [[ $# -ne 2 ]]; then
    usage
fi

variant="$1"
arch="$2"

case "$arch" in
    x86_64)
        platform="linux/amd64"
        ;;
    aarch64)
        platform="linux/arm64"
        ;;
    *)
        echo "Unsupported architecture: $arch" >&2
        usage
        ;;
esac

case "$variant" in
    standard)
        dockerfile="docker/Dockerfile.linux"
        suffix="linux-${arch}"
        ;;
    staticx)
        dockerfile="docker/Dockerfile.staticx"
        suffix="linux-staticx-${arch}"
        ;;
    *)
        echo "Unsupported variant: $variant" >&2
        usage
        ;;
esac

version=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
archive_name="TileMapService-v${version}-${suffix}.tar.gz"
out_dir="dist-ci/${variant}-${arch}"
artifacts_dir="artifacts"
image_tag="tilemapservice-${variant}-${arch}:ci"

rm -rf "$out_dir"
mkdir -p "$out_dir" "$artifacts_dir"

docker buildx build \
    --platform "$platform" \
    --build-arg "TARGETARCH_NAME=${arch}" \
    --load \
    -t "$image_tag" \
    -f "$dockerfile" \
    .

docker run --rm \
    -v "$(pwd)/${out_dir}:/output" \
    "$image_tag"

expected_archive="${out_dir}/${archive_name}"
if [[ ! -f "$expected_archive" ]]; then
    echo "Expected archive not found: $expected_archive" >&2
    exit 1
fi

cp "$expected_archive" "$artifacts_dir/"
echo "Created artifact: ${artifacts_dir}/$(basename "${expected_archive}")"

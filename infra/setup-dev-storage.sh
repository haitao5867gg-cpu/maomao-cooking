#!/bin/bash
# 创建 maomao-dev 存储账户及所有子资源
# 在 Mac 终端运行：bash infra/setup-dev-storage.sh
# 前提：已 az login

set -euo pipefail

RG="maomao-dev"
LOCATION="eastasia"
ACCOUNT="maomaodevstore"
SUB="a61796b5-4e9c-490d-9efc-d787af0ae1ed"

echo "=== 1/4 创建存储账户 ==="
az storage account create \
  --name "$ACCOUNT" \
  --resource-group "$RG" \
  --location "$LOCATION" \
  --sku Standard_LRS \
  --kind StorageV2 \
  --access-tier Hot \
  --subscription "$SUB" \
  --output table

echo ""
echo "=== 2/4 获取连接串 ==="
CONN=$(az storage account show-connection-string \
  --name "$ACCOUNT" \
  --resource-group "$RG" \
  --subscription "$SUB" \
  --output tsv)
echo "连接串: $CONN"

echo ""
echo "=== 3/4 创建队列 ==="
az storage queue create --name "dev-gpu-jobs" --connection-string "$CONN" --output table
az storage queue create --name "dev-gpu-jobs-poison" --connection-string "$CONN" --output table
az storage queue create --name "dev-pipeline-jobs" --connection-string "$CONN" --output table

echo ""
echo "=== 4/4 创建 Blob 容器 ==="
az storage container create --name "dev-gpu-output" --connection-string "$CONN" --output table
az storage container create --name "dev-videos" --connection-string "$CONN" --output table

echo ""
echo "============================================"
echo "全部完成！"
echo ""
echo "存储账户: $ACCOUNT"
echo "资源组:   $RG"
echo "区域:     $LOCATION"
echo ""
echo "连接串（复制到 2070Ti 的 .env-maomao 文件中）:"
echo "$CONN"
echo ""
echo "Table Storage 的表会由 worker 首次运行时自动创建。"
echo "============================================"

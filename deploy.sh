#!/bin/bash

# Thiết lập màu sắc hiển thị
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}===================================================${NC}"
echo -e "${BLUE}   HỆ THỐNG ĐẨY MÃ NGUỒN LÊN GITHUB & VERCEL       ${NC}"
echo -e "${BLUE}===================================================${NC}"

# 1. Kiểm tra thư mục làm việc
PROJECT_DIR="/Users/lenhutanh/.gemini/antigravity/scratch/ghn-dashboard"
cd "$PROJECT_DIR" || {
    echo -e "${RED}Lỗi: Không tìm thấy thư mục dự án tại $PROJECT_DIR${NC}"
    exit 1
}

# 2. Khởi tạo Git nếu chưa có
if [ ! -d ".git" ]; then
    echo -e "${YELLOW}[1/4] Khởi tạo Git repository mới...${NC}"
    git init
    git branch -M main
else
    echo -e "${GREEN}[1/4] Git repository đã được khởi tạo.${NC}"
fi

# 3. Add và Commit tất cả thay đổi
echo -e "${YELLOW}[2/4] Đang thêm và lưu thay đổi vào Git...${NC}"
git add .
git commit -m "feat: Cập nhật cấu hình Serverless API cho Vercel và sửa lỗi hiển thị dashboard" 2>/dev/null || echo -e "${GREEN}Mọi thay đổi đã được lưu trước đó.${NC}"

# 4. Thiết lập Git Remote
echo -e "${YELLOW}[3/4] Cấu hình địa chỉ GitHub remote...${NC}"
REMOTE_URL="https://github.com/tanhle95-bot/GHN---Dashboard.git"
git remote remove origin 2>/dev/null
git remote add origin "$REMOTE_URL"
echo -e "${GREEN}Đã liên kết thành công với: $REMOTE_URL${NC}"

# 5. Đẩy mã nguồn lên GitHub
echo -e "${BLUE}===================================================${NC}"
echo -e "${YELLOW}[4/4] Bắt đầu đẩy mã nguồn lên GitHub...${NC}"
echo -e "${YELLOW}Lưu ý: Nếu được yêu cầu, hãy đăng nhập hoặc nhập Personal Access Token của bạn.${NC}"
echo -e "${BLUE}===================================================${NC}"

if git push -u origin main; then
    echo -e "\n${GREEN}===================================================${NC}"
    echo -e "${GREEN}  ĐẨY MÃ NGUỒN LÊN GITHUB THÀNH CÔNG!              ${NC}"
    echo -e "${GREEN}===================================================${NC}"
    echo -e "\n${BLUE}BƯỚC TIẾP THEO ĐỂ TRIỂN KHAI LÊN VERCEL:${NC}"
    echo -e "1. Truy cập: ${YELLOW}https://vercel.com/new?teamSlug=tanhle95-9873s-projects${NC}"
    echo -e "2. Chọn Repository ${GREEN}ghn-dashboard${NC} và nhấn ${GREEN}Import${NC}."
    echo -e "3. Nhấn nút ${GREEN}Deploy${NC} để hoàn tất."
else
    echo -e "\n${RED}===================================================${NC}"
    echo -e "${RED}  LỖI: KHÔNG THỂ ĐẨY MÃ NGUỒN LÊN GITHUB            ${NC}"
    echo -e "${RED}===================================================${NC}"
    echo -e "${YELLOW}Hướng dẫn sửa lỗi:${NC}"
    echo -e "1. Đảm bảo tài khoản GitHub của bạn có quyền ghi vào repository này."
    echo -e "2. Nếu bạn chưa có Personal Access Token (PAT), hãy tạo một cái tại:"
    echo -e "   Settings -> Developer Settings -> Personal Access Tokens -> Tokens (classic)"
    echo -e "   Sau đó chạy lại lệnh: ${GREEN}git push https://<TOKEN>@github.com/tanhle95-bot/ghn-dashboard.git main${NC}"
fi

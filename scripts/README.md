# Hướng dẫn: generate_env_secrets.py

Tệp này mô tả cách sử dụng script `generate_env_secrets.py` để tự động sinh các giá trị "nhạy cảm" (mật khẩu, token, key...) trong file `.env` của môi trường Supabase local.

Nội dung chính
- Vị trí script: `supabase/scripts/generate_env_secrets.py`
- Mục đích: phát hiện các khóa nhạy cảm trong file `.env` (ví dụ: `POSTGRES_PASSWORD`, `JWT_SECRET`, `ANON_KEY`, `SERVICE_ROLE_KEY`, `SECRET_KEY_BASE`, `SMTP_PASS`, `LOGFLARE_*`, `OPENAI_API_KEY`, ...) và sinh các giá trị an toàn để thay thế.

Lệnh sử dụng (trên Windows cmd)

- Dry-run (chỉ in các thay đổi được đề xuất):

```cmd
python supabase\scripts\generate_env_secrets.py --env supabase\docker\.env --dry-run
```

- Ghi ra file khác (không ghi đè file nguồn):

```cmd
python supabase\scripts\generate_env_secrets.py --env supabase\docker\.env --output supabase\docker\.env.generated
```

- Ghi đè trực tiếp file nguồn (thao tác nguy hiểm — kiểm tra kỹ trước khi dùng):

```cmd
python supabase\scripts\generate_env_secrets.py --env supabase\docker\.env --in-place
```

- Sinh kết quả lặp lại (dùng seed):

```cmd
python supabase\scripts\generate_env_secrets.py --env supabase\docker\.env --dry-run --seed 42
```

Ghi chú về tuỳ chỉnh
- Nếu bạn muốn cung cấp giá trị cố định (thay vì sinh ngẫu nhiên) cho một key cụ thể, đặt biến môi trường `GENERATE_<KEY>` trước khi chạy. Ví dụ trên Windows cmd:

```cmd
set GENERATE_POSTGRES_PASSWORD=myfixedpassword
python supabase\scripts\generate_env_secrets.py --env supabase\docker\.env --in-place
```

Các giới hạn & cảnh báo bảo mật
- Script này chỉ giúp sinh các giá trị mẫu cho môi trường local/dev. Đừng commit các file `.env` chứa secrets vào git public.
- Kiểm tra kỹ file đầu ra trước khi dùng vào môi trường production. Với production, dùng secret manager chuyên dụng (Vault, AWS Secrets Manager, GCP Secret Manager, Azure Key Vault, v.v.).
- `--in-place` sẽ ghi đè file nguồn ngay lập tức — hãy backup trước nếu cần.

Gợi ý tích hợp
- Có thể thêm bước này vào quy trình khởi tạo local (Makefile, npm script) để tự động sinh `.env.generated` và yêu cầu người dùng review.

Ví dụ Makefile (ý tưởng):

```makefile
generate-env:
    python supabase/scripts/generate_env_secrets.py --env supabase/docker/.env --output supabase/docker/.env.generated
```

Hỗ trợ
- Nếu có yêu cầu mở rộng danh sách key mặc định, hãy chỉnh file `supabase/scripts/generate_env_secrets.py` và thêm generator cho key tương ứng.

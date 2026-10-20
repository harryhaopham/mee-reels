# MEE Pillar 3 reel log

| Ngày | Lỗi đã dạy | File | Link raw | Buffer id / status | Doc |
|---|---|---|---|---|---|
| 11/10/2026 | I very like it → I really like it | mee_reel_i_very_like_it.mp4 | https://raw.githubusercontent.com/harryhaopham/mee-reels/main/mee_reel_i_very_like_it.mp4 | (xem content log) | |
| 14/10/2026 | I'm agree → I agree | mee_reel_im_agree.mp4 | https://raw.githubusercontent.com/harryhaopham/mee-reels/main/mee_reel_im_agree.mp4 | 6acede4f1f3f10bcb7a96a1a / scheduled 14/10 19:00 (draft cũ được hoàn thiện) | https://docs.google.com/document/d/1xF7etu_wKrlkaPYLm2t6Ll-YWDi717QLmJ6hqEmtbZA/edit |

Ghi chú lỗi đã gặp:
- 14/10: gạch "'m" trong "I'm agree." trông như gạch cả "I'm" (vạch tràn 12px mỗi bên). Cảnh wrong nên viết dạng đầy đủ ("I am agree.", strike "am") để vạch gạch rõ.
- 14/10: python3 trong sandbox là /usr/local/bin/python3; cài numpy/pillow bằng `python3 -m pip` chứ không dùng `pip` trần.
| 20/10/2026 | He don't → He doesn't | mee_reel_he_dont.mp4 | https://raw.githubusercontent.com/harryhaopham/mee-reels/main/mee_reel_he_dont.mp4 | 6ad74cc03935fb9401230b1a / scheduled 20/10 19:00 | https://docs.google.com/document/d/1cKPKcisClqNL4eho2zHSgXGXwtKByTgfV2ASgCu0WZo/edit |
- 20/10: python3 hệ thống có PIL hỏng (dist-packages), pip install không đủ. Dùng venv: `python3 -m venv /tmp/venv && /tmp/venv/bin/pip install numpy pillow` rồi chạy `/tmp/venv/bin/python scripts/mee_reel.py ...`.
- 20/10: assets/ (logo, nhân vật) đã có sẵn trong repo, không cần mở Canva.

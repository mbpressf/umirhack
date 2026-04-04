# Server Deploy

Первичная установка на Ubuntu:

```bash
chmod +x deploy/server/first_setup.sh deploy/server/update.sh
./deploy/server/first_setup.sh
```

Обычное обновление после `git push`:

```bash
cd /opt/umirhack
./deploy/server/update.sh
```

Перед первым запуском при необходимости заполните `.env`:

- `VK_API_TOKEN`
- `APP_PORT`
- `MADRIGAL_AUTO_REFRESH_*`

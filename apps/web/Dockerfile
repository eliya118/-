FROM node:22.22.0-bookworm-slim@sha256:dd9d21971ec4395903fa6143c2b9267d048ae01ca6d3ea96f16cb30df6187d94 AS build
WORKDIR /src
RUN corepack enable && corepack prepare pnpm@10.33.4 --activate
COPY apps/web/package.json apps/web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY apps/web/ ./
RUN pnpm build

FROM build AS test
CMD ["pnpm", "test"]

FROM nginxinc/nginx-unprivileged:1.29.3@sha256:74adf8fc6c9e7290a810505e0d0384fa370b6ec1ce02547eecff77e2921ee24f
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist /usr/share/nginx/html
EXPOSE 8080

# Slideshow Player — Cloudflare Worker

## Setup

### 1. Create R2 bucket
```
wrangler r2 bucket create slideshow-studio
```

### 2. Create D1 database
```
wrangler d1 create slideshow-studio-db
```
Copy the database_id and update wrangler.toml

### 3. Run D1 schema
```
wrangler d1 execute slideshow-studio-db --file=d1_schema.sql
```

### 4. Deploy worker
```
wrangler deploy
```

### 5. Add DNS in Cloudflare dashboard
- CNAME: share.calgarydhamaka.com → your-worker.workers.dev

### 6. Update .env in Flask app
```
CF_ACCOUNT_ID=your_account_id
CF_R2_BUCKET=slideshow-studio
CF_D1_ID=your_d1_database_id
CF_API_TOKEN=your_api_token_with_r2_and_d1_write
```

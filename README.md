# EnGarde Subscription Sync Service

Microservice for synchronizing Langflow templates to users based on subscription tiers and enabled Walker Agents.

## Features

- ✅ **Subscription Tier Gating**: Users only receive templates for their subscription level
- ✅ **Walker Agent Gating**: Walker Agents are only synced if specifically enabled for the user
- ✅ **Free Tier Access**: All users receive En Garde Flows (free tier templates)
- ✅ **Automatic Folder Management**: Creates "En Garde" folder structure for non-admin users
- ✅ **Service-to-Service Auth**: Secure token-based authentication
- ✅ **Cost-Efficient**: Railway sleep mode - only wakes on requests (~$0-2/month)
- ✅ **Fast Deployment**: ~30 second deploys vs 10+ minutes for Langflow

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Railway Project                       │
│                                                          │
│  ┌──────────────┐        ┌──────────────────────────┐  │
│  │  Langflow    │        │  Subs Sync Service       │  │
│  │  Service     │        │  (This microservice)     │  │
│  └──────┬───────┘        └─────────┬────────────────┘  │
│         │                           │                   │
│         └────────┬──────────────────┘                   │
│                  │                                       │
│         ┌────────▼──────────┐                           │
│         │  En-Garde-FlowDB  │                           │
│         │    (PostgreSQL)    │                           │
│         └────────┬──────────┘                           │
│                  │                                       │
│  ┌───────────────▼──────────────────┐                   │
│  │   EnGarde Backend (Onside)       │                   │
│  │  Provides: User subscription     │                   │
│  │   tier and enabled walker agents │                   │
│  └──────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────┘
```

## Admin Folder Structure

Admins (superusers) maintain templates in two folders:

### 1. "Walker Agents" Folder
Contains walker agent templates (subscription-gated):
- SEO Walker Agent (requires: Pro tier + SEO enabled)
- Content Walker Agent (requires: Pro tier + Content enabled)
- Paid Ads Walker Agent (requires: Pro tier + Paid Ads enabled)
- Audience Intelligence Walker Agent (requires: Enterprise tier + Audience Intel enabled)

### 2. "En Garde Flows" Folder
Contains free-tier templates (everyone gets these):
- Basic SEO Flow
- Content Calendar Flow
- Social Media Scheduler
- etc.

## Non-Admin Folder Structure

Non-admin users receive one "En Garde" folder containing:
- **Walker Agents** (filtered by subscription tier + enabled agents)
- **En Garde Flows** (all users receive - FREE tier)

## Template Metadata Format

Admin templates must include metadata in the description field:

```json
{
  "user_description": "This flow helps you optimize SEO campaigns...",
  "template_metadata": {
    "required_tier": "pro",
    "walker_agent_type": "seo",
    "category": "walker_agents",
    "features": ["keyword_research", "competitor_analysis"],
    "version": "1.0.0"
  }
}
```

### Metadata Fields

| Field | Values | Description |
|-------|--------|-------------|
| `required_tier` | `free`, `pro`, `enterprise`, `agency` | Minimum tier required |
| `walker_agent_type` | `seo`, `content`, `paid_ads`, `audience_intelligence` | Walker agent type (null for En Garde Flows) |
| `category` | `walker_agents`, `engarde_flows` | Template category |
| `features` | Array of strings | Features this template provides |
| `version` | Semantic version (e.g., "1.0.0") | Template version |

## API Endpoints

### 1. Sync User Templates

```http
POST /sync/{user_id}?force_sync=false
Authorization: Bearer <service-token>
```

**Response:**
```json
{
  "user_id": "uuid",
  "sync_timestamp": "2026-01-19T20:00:00Z",
  "status": "success",
  "new_flows_added": [...],
  "flows_denied": [...],
  "total_templates_available": 10,
  "total_templates_accessible": 6,
  "total_templates_synced": 5,
  "subscription_tier": "pro",
  "enabled_walker_agents": ["seo", "content"]
}
```

### 2. Get Sync Status

```http
GET /sync/{user_id}/status
Authorization: Bearer <service-token>
```

Returns current sync status, accessible templates, and upgrade opportunities.

### 3. Check Template Access

```http
POST /sync/{user_id}/check-access/{template_id}
Authorization: Bearer <service-token>
```

Check if a specific user can access a specific template.

### 4. Health Check

```http
GET /health
```

Returns service health status.

## Deployment

### Prerequisites

1. Railway account
2. Langflow deployed with PostgreSQL database
3. EnGarde backend API endpoint for user access control

### Step 1: Create GitHub Repository

```bash
# From subs_sync directory
git init
git add .
git commit -m "Initial commit: EnGarde Subscription Sync Service"
git remote add origin https://github.com/EnGardeHQ/subs-sync.git
git push -u origin main
```

### Step 2: Deploy to Railway

1. **Create New Service:**
   ```bash
   # Link to Railway project
   cd subs_sync
   railway link

   # Create new service
   railway service create subs-sync
   ```

2. **Configure Environment Variables:**
   ```bash
   # Set database URL (same as Langflow)
   railway variables set LANGFLOW_DATABASE_URL="<postgres-url>"

   # Set EnGarde backend API
   railway variables set ENGARDE_API_URL="https://api.engarde.media"
   railway variables set ENGARDE_API_KEY="<your-api-key>"

   # Set service token (generate secure random token)
   railway variables set SUBS_SYNC_SERVICE_TOKEN="<secure-random-token>"

   # Set environment
   railway variables set ENV="production"
   ```

3. **Deploy:**
   ```bash
   railway up
   ```

4. **Enable Sleep Mode** (cost savings):
   - Go to Railway dashboard → subs-sync service → Settings
   - Enable "Sleep Application When Idle"
   - Service will wake automatically on HTTP requests

### Step 3: Integrate with EnGarde Backend

Update EnGarde backend to call sync service after SSO login:

```typescript
// After successful SSO login
const syncResponse = await fetch(
  `${process.env.SUBS_SYNC_URL}/sync/${userId}`,
  {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${process.env.SUBS_SYNC_SERVICE_TOKEN}`,
      'Content-Type': 'application/json'
    }
  }
);
```

## EnGarde Backend API Contract

The sync service expects EnGarde backend to provide this endpoint:

```http
GET /api/users/{user_id}/access-control
Authorization: Bearer <engarde-api-key>
```

**Response:**
```json
{
  "user_id": "uuid",
  "subscription_tier": "pro",
  "enabled_walker_agents": ["seo", "content", "paid_ads"],
  "tier_limits": {
    "max_flows": 50,
    "max_walker_agents": 3,
    "max_campaigns": 10,
    "api_rate_limit": 1000
  },
  "is_active": true,
  "tenant_id": "tenant-uuid"
}
```

## Cost Analysis

### Infrastructure Costs (Monthly)

| Component | Configuration | Cost |
|-----------|--------------|------|
| **Railway Service** | 256MB RAM, 0.1 vCPU, Sleep Mode | **$0-2/month** |
| **Database** | Shared with Langflow | $0 (no additional cost) |
| **Build Minutes** | ~30 seconds per deploy | < $0.50/month |
| **Total** | | **~$0-2.50/month** |

### vs. Build-from-Source Approach

| Metric | Microservice | Build-from-Source |
|--------|-------------|-------------------|
| Monthly Cost | $0-2.50 | $7-15 |
| Deploy Time | 30 seconds | 15-20 minutes |
| Maintenance | Low | High |
| Langflow Upgrades | Easy (unchanged) | Hard (merge conflicts) |

## Development

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your values

# Run server
uvicorn app.main:app --reload --port 8000
```

### Testing

```bash
# Test health endpoint
curl http://localhost:8000/health

# Test sync (requires valid user_id and token)
curl -X POST "http://localhost:8000/sync/<user-id>" \
  -H "Authorization: Bearer <token>"
```

## Monitoring

### Railway Logs

```bash
# View logs
railway logs

# Follow logs
railway logs --follow
```

### Health Checks

Railway automatically monitors the `/health` endpoint every 30 seconds.

## Troubleshooting

### Service Not Responding

**Issue**: Service is sleeping and not waking up.

**Solution**:
1. Check Railway dashboard - service status should be "Sleeping"
2. Send HTTP request - service should wake within 1-2 seconds
3. If still not responding, check logs: `railway logs`

### Database Connection Errors

**Issue**: `asyncpg.exceptions.InvalidCatalogNameError`

**Solution**: Verify `LANGFLOW_DATABASE_URL` environment variable:
```bash
railway variables get LANGFLOW_DATABASE_URL
```

### Authentication Failures

**Issue**: 401 Unauthorized responses

**Solution**: Verify service token matches between EnGarde backend and sync service:
```bash
railway variables get SUBS_SYNC_SERVICE_TOKEN
```

### Templates Not Syncing

**Issue**: User not receiving expected templates

**Solution**:
1. Check user's subscription tier in EnGarde backend
2. Verify template metadata in Langflow admin folders
3. Check sync service logs for access denial reasons

## Security Considerations

1. **Service Token**: Use cryptographically secure random tokens (32+ characters)
2. **Database Access**: Service has full read/write access to Langflow DB - secure accordingly
3. **EnGarde API Key**: Protect API key - don't commit to git
4. **CORS**: In production, restrict CORS to EnGarde domains only

## Future Enhancements

- [ ] Template version tracking and update notifications
- [ ] Webhook triggers for real-time sync
- [ ] Template usage analytics
- [ ] A/B testing for template variations
- [ ] Template rollback feature
- [ ] Admin UI for template management

## Support

For issues or questions:
- **Logs**: `railway logs --service subs-sync`
- **GitHub Issues**: https://github.com/EnGardeHQ/subs-sync/issues
- **Documentation**: This README

## License

MIT License - EnGarde Media 2026

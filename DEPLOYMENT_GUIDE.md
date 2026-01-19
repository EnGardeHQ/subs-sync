# Subs Sync Service - Railway Deployment Guide

## ✅ Completed

- [x] GitHub repository created: https://github.com/EnGardeHQ/subs-sync
- [x] Code pushed to main branch
- [x] Direct database access implemented (dual database architecture)

## 📋 Prerequisites

You need access to:
1. Railway project with these existing services:
   - `En-Garde-FlowDB` (Langflow PostgreSQL database)
   - `Postgres` (EnGarde main application database)
2. EnGarde database must have these tables:
   - `users` (with `subscription_tier` column)
   - `user_walker_agents` (for walker agent enablement)

## 🚀 Deployment Steps

### Step 1: Create Railway Service from GitHub

1. **Go to Railway Dashboard**: https://railway.app
2. **Select your EnGarde project**
3. **Click "New" → "GitHub Repo"**
4. **Select repository**: `EnGardeHQ/subs-sync`
5. **Service name**: `subs-sync`
6. **Click "Deploy"**

Railway will automatically detect the `railway.toml` and `Dockerfile`.

### Step 2: Configure Environment Variables

In Railway dashboard → `subs-sync` service → Variables tab:

```bash
# 1. Langflow Database (for templates and flows)
LANGFLOW_DATABASE_URL = ${{En-Garde-FlowDB.DATABASE_URL}}

# 2. EnGarde Main Database (for subscription tiers and walker agents)
ENGARDE_DATABASE_URL = ${{Postgres.DATABASE_URL}}

# 3. Service Authentication Token (generate a secure random token)
SUBS_SYNC_SERVICE_TOKEN = <paste-output-of-command-below>

# 4. Environment
ENV = production

# 5. Log Level (optional)
LOG_LEVEL = INFO
```

**Generate secure token:**
```bash
openssl rand -hex 32
```

Copy the output and paste as `SUBS_SYNC_SERVICE_TOKEN`.

### Step 3: Enable Sleep Mode (Cost Savings)

1. Go to **Settings** tab for `subs-sync` service
2. Scroll to **Sleep Application**
3. **Enable** "Sleep application when idle"
4. Click **Save**

This will reduce costs to ~$0-2/month (service sleeps when not in use).

### Step 4: Get Service URL

1. Go to **Settings** tab → **Networking**
2. Click **Generate Domain**
3. Copy the public URL (e.g., `https://subs-sync-production.up.railway.app`)
4. Save this URL - you'll need it for EnGarde backend integration

### Step 5: Verify Deployment

Test the health endpoint:

```bash
curl https://your-subs-sync-url.up.railway.app/health
```

**Expected Response:**
```json
{
  "service": "subscription-sync",
  "status": "healthy",
  "version": "1.0.0"
}
```

## 🔗 EnGarde Backend Integration

After deployment, update your EnGarde backend (Onside) to call the sync service after SSO login:

### Option A: Add to SSO Login Handler

```typescript
// In your SSO login handler (after user is authenticated)
async function handleSSOLogin(userId: string) {
  // ... existing SSO logic ...

  // Trigger template sync (non-blocking)
  try {
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

    if (!syncResponse.ok) {
      console.error('Template sync failed:', await syncResponse.text());
    } else {
      const result = await syncResponse.json();
      console.log('Template sync completed:', result);
    }
  } catch (error) {
    // Non-critical - don't block login
    console.error('Template sync error:', error);
  }

  // ... continue with login ...
}
```

### Option B: Add to User Subscription Change Handler

```typescript
// When user upgrades/downgrades subscription or enables walker agents
async function handleSubscriptionChange(userId: string) {
  await fetch(
    `${process.env.SUBS_SYNC_URL}/sync/${userId}?force_sync=true`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${process.env.SUBS_SYNC_SERVICE_TOKEN}`,
      }
    }
  );
}
```

### EnGarde Backend Environment Variables

Add to your Onside (EnGarde backend) service:

```bash
SUBS_SYNC_URL = <your-subs-sync-railway-url>
SUBS_SYNC_SERVICE_TOKEN = <same-token-as-subs-sync-service>
```

## 🗄️ Database Setup

### EnGarde Database Schema

Ensure your EnGarde PostgreSQL database has these tables:

```sql
-- Users table (should already exist)
ALTER TABLE users
ADD COLUMN IF NOT EXISTS subscription_tier VARCHAR(50) DEFAULT 'free';

CREATE INDEX IF NOT EXISTS idx_users_subscription_tier
ON users(subscription_tier);

-- User walker agents table (create if doesn't exist)
CREATE TABLE IF NOT EXISTS user_walker_agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    walker_agent_type VARCHAR(50) NOT NULL,
    -- Values: 'seo', 'content', 'paid_ads', 'audience_intelligence'
    enabled BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, walker_agent_type)
);

CREATE INDEX IF NOT EXISTS idx_user_walker_agents_user_id
ON user_walker_agents(user_id);

CREATE INDEX IF NOT EXISTS idx_user_walker_agents_enabled
ON user_walker_agents(enabled);
```

### Test Data

Create a test user with subscription tier and walker agents:

```sql
-- Update existing user's subscription tier
UPDATE users
SET subscription_tier = 'pro'
WHERE email = 'test@engarde.com';

-- Enable walker agents for user
INSERT INTO user_walker_agents (user_id, walker_agent_type, enabled) VALUES
((SELECT id FROM users WHERE email = 'test@engarde.com'), 'seo', true),
((SELECT id FROM users WHERE email = 'test@engarde.com'), 'content', true)
ON CONFLICT (user_id, walker_agent_type)
DO UPDATE SET enabled = EXCLUDED.enabled;
```

## 📊 Testing

### Test 1: Health Check

```bash
curl https://your-subs-sync-url.up.railway.app/health
```

### Test 2: Sync a User

```bash
curl -X POST "https://your-subs-sync-url.up.railway.app/sync/<user-id>" \
  -H "Authorization: Bearer <your-service-token>" \
  -H "Content-Type: application/json"
```

**Expected Response:**
```json
{
  "user_id": "uuid",
  "sync_timestamp": "2026-01-19T20:00:00Z",
  "status": "success",
  "new_flows_added": [...],
  "total_templates_accessible": 6,
  "subscription_tier": "pro",
  "enabled_walker_agents": ["seo", "content"]
}
```

### Test 3: Check Sync Status

```bash
curl "https://your-subs-sync-url.up.railway.app/sync/<user-id>/status" \
  -H "Authorization: Bearer <your-service-token>"
```

## 🎯 Admin Template Setup in Langflow

For the sync to work, admins need to create templates in Langflow:

### Step 1: Create Admin Folders

In Langflow UI (as superuser):

1. Create folder: **"Walker Agents"**
2. Create folder: **"En Garde Flows"**

### Step 2: Add Template Metadata

For each template flow, edit the description to include metadata (JSON format):

**Example for Walker Agent Template:**
```json
{
  "user_description": "This flow optimizes SEO campaigns using AI-powered analysis...",
  "template_metadata": {
    "required_tier": "pro",
    "walker_agent_type": "seo",
    "category": "walker_agents",
    "features": ["keyword_research", "competitor_analysis", "content_optimization"],
    "version": "1.0.0"
  }
}
```

**Example for Free Tier Template:**
```json
{
  "user_description": "Basic SEO workflow for all users...",
  "template_metadata": {
    "required_tier": "free",
    "walker_agent_type": null,
    "category": "engarde_flows",
    "features": ["keyword_tracking"],
    "version": "1.0.0"
  }
}
```

### Template Metadata Fields

| Field | Values | Description |
|-------|--------|-------------|
| `required_tier` | `free`, `pro`, `enterprise`, `agency` | Minimum tier required |
| `walker_agent_type` | `seo`, `content`, `paid_ads`, `audience_intelligence` or `null` | Walker agent type |
| `category` | `walker_agents`, `engarde_flows` | Template category |
| `features` | Array of strings | Features provided |
| `version` | Semantic version | Template version |

## 📈 Monitoring

### View Logs

```bash
railway logs --service subs-sync --follow
```

### Check Service Status

```bash
railway status --service subs-sync
```

### Monitor Costs

- Go to Railway dashboard → Project → Usage
- Subs-sync should show ~$0-2/month with sleep mode enabled

## 🐛 Troubleshooting

### Service Returns 500 Error

**Check logs:**
```bash
railway logs --service subs-sync --tail 100
```

**Common issues:**
- Database connection URL incorrect
- Missing tables in EnGarde database
- Service token mismatch

### Templates Not Syncing

**Verify:**
1. Admin templates exist in Langflow (check "Walker Agents" and "En Garde Flows" folders)
2. Templates have proper metadata in description field
3. User subscription tier is set in EnGarde database
4. Walker agents are enabled for user in `user_walker_agents` table

### Database Connection Errors

**Test connections:**
```sql
-- Test Langflow DB
psql "$LANGFLOW_DATABASE_URL" -c "SELECT COUNT(*) FROM flow;"

-- Test EnGarde DB
psql "$ENGARDE_DATABASE_URL" -c "SELECT COUNT(*) FROM users;"
```

## 📚 Additional Resources

- **Full README**: https://github.com/EnGardeHQ/subs-sync/blob/main/README.md
- **GitHub Repository**: https://github.com/EnGardeHQ/subs-sync
- **Railway Docs**: https://docs.railway.app

## ✅ Checklist

- [ ] Railway service created from GitHub repo
- [ ] Environment variables configured
- [ ] Sleep mode enabled
- [ ] Service URL generated and saved
- [ ] Health check successful
- [ ] EnGarde database schema updated
- [ ] Test user created with subscription tier
- [ ] Admin templates created in Langflow
- [ ] Template metadata added to descriptions
- [ ] EnGarde backend integration completed
- [ ] End-to-end sync tested successfully

## 🎉 Next Steps

Once deployed and tested:

1. **Create Admin Templates**: Add your walker agent templates to Langflow
2. **Enable Walker Agents**: Configure which agents each user has access to
3. **Test with Real Users**: Verify sync works on SSO login
4. **Monitor Logs**: Watch for any sync errors
5. **Iterate**: Update templates and metadata as needed

---

**Questions or Issues?**
- Check logs: `railway logs --service subs-sync`
- Review README: https://github.com/EnGardeHQ/subs-sync
- Check GitHub Issues: https://github.com/EnGardeHQ/subs-sync/issues

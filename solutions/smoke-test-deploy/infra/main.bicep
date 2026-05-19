targetScope = 'resourceGroup'

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Environment name: dev, staging, prod')
@allowed(['dev', 'staging', 'prod'])
param environmentName string = 'dev'

@description('Unique resource token — auto-generated if not provided')
param resourceToken string = uniqueString(resourceGroup().id, environmentName)

@description('Tags applied to all resources')
param tags object = {
  project: 'idea-generator-agent'
  solution: 'smoke-test-deploy'
  environment: environmentName
  generatedBy: 'idea-generator-agent'
  generatedAt: '2026-05-19T03:33:09Z'
}

// ── Monitoring ─────────────────────────────────────────────────────────────
module monitoring 'br/public:avm/res/operational-insights/workspace:0.7.0' = {
  name: 'logAnalyticsDeploy'
  params: {
    name: '${resourceToken}-logs'
    location: location
    tags: tags
  }
}

// ── Solution-specific resources ───────────────────────────────────────────
// RAG Solution — Azure AI Search + OpenAI
module search 'br/public:avm/res/search/search-service:0.7.1' = {
  name: 'searchDeploy'
  params: {
    name: '${resourceToken}-search'
    location: location
    sku: 'standard'
    semanticSearch: 'standard'
  }
}
module openai 'br/public:avm/res/cognitive-services/account:0.7.2' = {
  name: 'openaiDeploy'
  params: {
    name: '${resourceToken}-openai'
    location: location
    kind: 'OpenAI'
    deployments: [
      { name: 'gpt-4o', model: { format: 'OpenAI', name: 'gpt-4o', version: '2024-11-20' }, sku: { name: 'GlobalStandard', capacity: 30 } }
      { name: 'text-embedding-ada-002', model: { format: 'OpenAI', name: 'text-embedding-ada-002', version: '2' }, sku: { name: 'Standard', capacity: 120 } }
    ]
  }
}

output solutionName string = 'smoke-test-deploy'
output environment string = environmentName
output resourceToken string = resourceToken

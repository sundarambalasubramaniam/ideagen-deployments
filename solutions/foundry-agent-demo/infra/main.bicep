targetScope = 'resourceGroup'

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Environment name: dev, staging, prod')
@allowed(['dev', 'staging', 'prod'])
param environmentName string = 'dev'

@description('Unique resource token — auto-generated if not provided')
param resourceToken string = uniqueString(resourceGroup().id, environmentName)

@description('Foundry model deployment name used by the agent')
param modelDeploymentName string = 'gpt-4o-mini'

@description('Tags applied to all resources')
param tags object = {
  project: 'idea-generator-agent'
  solution: 'foundry-agent-demo'
  environment: environmentName
  generatedBy: 'idea-generator-agent'
  generatedAt: '2026-05-19T05:10:20Z'
}

var acrName = toLower(replace('${resourceToken}acr', '-', ''))
var foundryAccountName = '${resourceToken}-ai'
var foundryProjectName = 'proj-${resourceToken}'

// ── Monitoring ─────────────────────────────────────────────────────────────
module monitoring 'br/public:avm/res/operational-insights/workspace:0.7.0' = {
  name: 'logAnalyticsDeploy'
  params: {
    name: '${resourceToken}-logs'
    location: location
    tags: tags
  }
}

// ── User-assigned managed identity (used by Container App) ────────────────
resource uami 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${resourceToken}-uami'
  location: location
  tags: tags
}

// ── Azure AI Foundry: AI Services account + project + model deployment ────
resource foundry 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: foundryAccountName
  location: location
  tags: tags
  kind: 'AIServices'
  sku: { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    customSubDomainName: foundryAccountName
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
    allowProjectManagement: true
  }
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2024-10-01' = {
  parent: foundry
  name: foundryProjectName
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {}
}

resource gptDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: foundry
  name: modelDeploymentName
  sku: { name: 'GlobalStandard', capacity: 10 }
  properties: {
    model: { format: 'OpenAI', name: 'gpt-4o-mini', version: '2024-07-18' }
  }
}

// Grant the UAMI 'Azure AI User' on the Foundry account so the agent can call models.
resource aiUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: foundry
  name: guid(foundry.id, uami.id, '53ca6127-db72-4b80-b1b0-d745d6d5456d')
  properties: {
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '53ca6127-db72-4b80-b1b0-d745d6d5456d')
  }
}

// ── Container Registry ────────────────────────────────────────────────────
resource acr 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: acrName
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

// Grant the UAMI 'AcrPull' so Container Apps can pull images.
resource acrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: acr
  name: guid(acr.id, uami.id, '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  properties: {
    principalId: uami.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  }
}

// ── Container Apps Environment ────────────────────────────────────────────
resource acaEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${resourceToken}-acaenv'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'azure-monitor'
    }
  }
}

// ── Solution-specific add-on resources (technique-driven) ─────────────────
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

output solutionName string = 'foundry-agent-demo'
output environment string = environmentName
output resourceToken string = resourceToken
output acrLoginServer string = acr.properties.loginServer
output acrName string = acr.name
output identityResourceId string = uami.id
output identityClientId string = uami.properties.clientId
output acaEnvironmentId string = acaEnv.id
output foundryProjectEndpoint string = 'https://${foundryAccountName}.services.ai.azure.com/api/projects/${foundryProjectName}'
output modelDeploymentName string = gptDeployment.name

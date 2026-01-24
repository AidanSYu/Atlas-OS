# Atlas 2.0 - System Verification Script
# Checks that the redesign is complete

Write-Host "=" * 70
Write-Host "Atlas 2.0 - System Verification"
Write-Host "=" * 70

$errors = 0
$warnings = 0

# Check for Neo4j removal
Write-Host "`n[1/9] Checking Neo4j removal..."
$activeFiles = Get-ChildItem "backend\*.py" -Exclude "server_old.py","server_demo.py"
$neo4jCheck = $false
foreach ($file in $activeFiles) {
    if (Select-String -Path $file.FullName -Pattern "neo4j" -Quiet) {
        Write-Host "  Found neo4j in: $($file.Name)" -ForegroundColor Red
        $neo4jCheck = $true
    }
}
if ($neo4jCheck) {
    Write-Host "❌ FAIL: Neo4j references still exist in active Python files" -ForegroundColor Red
    $errors++
} else {
    Write-Host "✅ PASS: No Neo4j references in active Python files" -ForegroundColor Green
}

# Check for required new modules
Write-Host "`n[2/9] Checking new modules exist..."
$requiredFiles = @(
    "backend\database.py",
    "backend\vector_store.py",
    "backend\knowledge_graph.py",
    "backend\document_store.py",
    "backend\query_orchestrator.py",
    "backend\init_db.py"
)

foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "✅ $file exists" -ForegroundColor Green
    } else {
        Write-Host "❌ $file missing" -ForegroundColor Red
        $errors++
    }
}

# Check requirements.txt
Write-Host "`n[3/9] Checking dependencies..."
$requirements = Get-Content "backend\requirements.txt" -Raw

if ($requirements -match "qdrant-client") {
    Write-Host "✅ qdrant-client in requirements" -ForegroundColor Green
} else {
    Write-Host "❌ qdrant-client missing" -ForegroundColor Red
    $errors++
}

if ($requirements -match "sqlalchemy") {
    Write-Host "✅ sqlalchemy in requirements" -ForegroundColor Green
} else {
    Write-Host "❌ sqlalchemy missing" -ForegroundColor Red
    $errors++
}

if ($requirements -match "psycopg2") {
    Write-Host "✅ psycopg2 in requirements" -ForegroundColor Green
} else {
    Write-Host "❌ psycopg2 missing" -ForegroundColor Red
    $errors++
}

if ($requirements -match "neo4j") {
    Write-Host "⚠️  WARNING: neo4j still in requirements" -ForegroundColor Yellow
    $warnings++
}

if ($requirements -match "chromadb") {
    Write-Host "⚠️  WARNING: chromadb still in requirements" -ForegroundColor Yellow
    $warnings++
}

# Check config.py
Write-Host "`n[4/9] Checking configuration..."
$config = Get-Content "backend\config.py" -Raw

if ($config -match "POSTGRES") {
    Write-Host "✅ PostgreSQL configuration present" -ForegroundColor Green
} else {
    Write-Host "❌ PostgreSQL configuration missing" -ForegroundColor Red
    $errors++
}

if ($config -match "QDRANT") {
    Write-Host "✅ Qdrant configuration present" -ForegroundColor Green
} else {
    Write-Host "❌ Qdrant configuration missing" -ForegroundColor Red
    $errors++
}

if ($config -match "NEO4J") {
    Write-Host "⚠️  WARNING: Neo4j config still present" -ForegroundColor Yellow
    $warnings++
}

# Check documentation
Write-Host "`n[5/9] Checking documentation..."
$docs = @(
    "README.md",
    "ARCHITECTURE.md",
    "QUICKSTART.md",
    "EXAMPLE_QUERIES.md",
    "REDESIGN_SUMMARY.md"
)

foreach ($doc in $docs) {
    if (Test-Path $doc) {
        Write-Host "✅ $doc exists" -ForegroundColor Green
    } else {
        Write-Host "❌ $doc missing" -ForegroundColor Red
        $errors++
    }
}

# Check server.py structure
Write-Host "`n[6/9] Checking server.py..."
$server = Get-Content "backend\server.py" -Raw

if ($server -match "IngestionPipeline") {
    Write-Host "✅ IngestionPipeline imported" -ForegroundColor Green
} else {
    Write-Host "❌ IngestionPipeline not found" -ForegroundColor Red
    $errors++
}

if ($server -match "QueryOrchestrator") {
    Write-Host "✅ QueryOrchestrator imported" -ForegroundColor Green
} else {
    Write-Host "❌ QueryOrchestrator not found" -ForegroundColor Red
    $errors++
}

# Check database schema
Write-Host "`n[7/9] Checking database schema..."
$database = Get-Content "backend\database.py" -Raw

$tables = @("Document", "DocumentChunk", "Entity", "Relationship")
foreach ($table in $tables) {
    if ($database -match "class $table") {
        Write-Host "✅ $table table defined" -ForegroundColor Green
    } else {
        Write-Host "❌ $table table missing" -ForegroundColor Red
        $errors++
    }
}

# Check setup scripts
Write-Host "`n[8/9] Checking setup scripts..."
if (Test-Path "setup-atlas.ps1") {
    Write-Host "✅ Setup script exists" -ForegroundColor Green
} else {
    Write-Host "❌ Setup script missing" -ForegroundColor Red
    $errors++
}

# Check for old files that should be backed up
Write-Host "`n[9/9] Checking for old files..."
if (Test-Path "backend\server_old.py") {
    Write-Host "✅ Old server backed up" -ForegroundColor Green
} else {
    Write-Host "⚠️  WARNING: Old server not backed up" -ForegroundColor Yellow
    $warnings++
}

# Summary
Write-Host "`n" + "=" * 70
Write-Host "Verification Summary"
Write-Host "=" * 70

if ($errors -eq 0 -and $warnings -eq 0) {
    Write-Host "`n✅ ALL CHECKS PASSED!" -ForegroundColor Green
    Write-Host "`nThe system redesign is complete and ready to use."
    Write-Host "Run setup-atlas.ps1 to initialize the system."
} elseif ($errors -eq 0) {
    Write-Host "`n⚠️  All critical checks passed, but there are $warnings warning(s)" -ForegroundColor Yellow
    Write-Host "`nThe system should work, but review the warnings above."
} else {
    Write-Host "`n❌ FAILED: $errors critical error(s) and $warnings warning(s)" -ForegroundColor Red
    Write-Host "`nPlease fix the errors above before proceeding."
}

Write-Host "`nErrors: $errors"
Write-Host "Warnings: $warnings"
Write-Host "=" * 70

# Java 版 — 多Agent临床辅助决策系统

基于 **Spring Boot 3.3 + LangGraph4j + Spring AI** 构建。

## 环境要求

- Java 17+
- Maven 3.9+
- PostgreSQL 16

## 快速开始

```bash
# 1. 配置环境变量
export OPENAI_API_KEY=your-key-here

# 2. 构建
mvn clean package -DskipTests

# 3. 运行
java -jar target/clinical-decision-system-1.0.0.jar

# 4. 访问
# http://localhost:8080/api/v1/clinical/health
```

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/clinical/analyze` | 运行完整5-Agent Pipeline |
| GET  | `/api/v1/clinical/health` | 健康检查 |

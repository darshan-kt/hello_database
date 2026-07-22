# Database Basics

# What is a Database?

A **database** is an organized collection of data that allows us to **store, retrieve, update, and manage information efficiently**.

**Example:** Amazon stores customers, products, orders, and payments in databases instead of Excel files.

---

# Two Main Types of Databases

```text
Databases
│
├── Relational Database (SQL)
│     ├── PostgreSQL
│     ├── MySQL
│     ├── Oracle
│     └── SQL Server
│
└── Non-Relational Database (NoSQL)
      ├── Document DB
      │     └── MongoDB
      ├── Key-Value DB
      │     └── Redis
      ├── Column-Family DB
      │     └── Cassandra
      ├── Graph DB
      │     └── Neo4j
      └── Vector DB
            ├── Pinecone
            ├── Milvus
            ├── Weaviate
            ├── Qdrant
            └── Chroma
```

---

# 1. Relational Database (SQL)

Stores data in **tables** with rows and columns.

## Diagram

```text
Customers
+----+--------+
| ID | Name   |
+----+--------+
| 1  | John   |
| 2  | Alice  |
+----+--------+

Orders
+------+---------+
| ID   | User_ID |
+------+---------+
| 101  |    1    |
| 102  |    2    |
+------+---------+
```

## Characteristics

- Data stored in tables
- Fixed schema
- Uses SQL
- Supports relationships
- ACID transactions
- High consistency

## Examples

- PostgreSQL
- MySQL
- Oracle
- SQL Server

## When to Use

Choose a relational database when your data has strong relationships and consistency is critical.

## Real-World Examples

- Banking (accounts, transactions)
- Amazon (orders, payments)
- Hospital Management
- Student Management System
- HR & Payroll

---

# 2. Non-Relational Database (NoSQL)

Stores data without requiring tables.

## Example (Document)

```json
{
  "id": 1,
  "name": "John",
  "orders": [
    {
      "product": "Laptop",
      "price": 70000
    }
  ]
}
```

## Characteristics

- Flexible schema
- High scalability
- Fast reads/writes
- Handles large and changing datasets

## Examples

- MongoDB
- Redis
- Cassandra
- Neo4j

## When to Use

Choose NoSQL when data changes frequently or must scale across many servers.

## Real-World Examples

- WhatsApp chats
- Instagram posts
- YouTube comments
- IoT sensor data
- Session storage
- Caching

---

# Vector Database

A Vector Database is a **specialized NoSQL database** used for storing **embeddings (vectors)** and performing **similarity search**.

## Diagram

```text
Databases
│
└── Non-Relational Database (NoSQL)
      └── Vector DB
            ├── Pinecone
            ├── Milvus
            ├── Weaviate
            ├── Qdrant
            └── Chroma
```

## How It Works

```text
Question

"What is Artificial Intelligence?"

          │

Embedding Model

          │

[0.23, -0.54, 0.91, ...]

          │

Vector Database

          │

Find Similar Vectors

          │

Most Relevant Documents
```

## Characteristics

- Stores embeddings instead of rows
- Optimized for similarity search
- Used in AI applications
- Supports millions of vectors

## Examples

- Pinecone
- Milvus
- Weaviate
- Qdrant
- Chroma

## When to Use

- RAG (Retrieval-Augmented Generation)
- AI Chatbots
- Semantic Search
- Recommendation Systems
- Image Search

## Real-World Examples

- ChatGPT retrieving relevant documents
- Netflix recommending similar movies
- Spotify recommending songs
- Google Images finding similar images
- E-commerce product recommendations

---

# Quick Summary

| Database Type | Best Used For | Examples |
|---------------|---------------|----------|
| Relational (SQL) | Structured data with relationships | PostgreSQL, MySQL |
| NoSQL | Flexible, scalable data | MongoDB, Redis, Cassandra |
| Vector DB | AI similarity search | Pinecone, Milvus, Qdrant |

---
title: "Concurrency Design Patterns: From Fundamental Theory to Architecture"
published: false
description: "From the differences between 'concurrency' and 'parallelism' and Amdahl's Law to design strategies viewed through three layers (Architecture, Task, State). A comprehensive guide to the 'First Principles of Concurrency' required for robust system design in the AI era."
tags: ["concurrency", "designpatterns", "architecture", "performance"]
series: "Concurrency"
---

# Introduction

It is 2026. If you ask an AI agent to "speed up this process," it will return parallelized code in seconds.
However, how many engineers can logically explain **why that code becomes faster**, or **why it doesn't become as fast as expected**?

AI solves the "How" of implementation, but the "Why" and "Structure" that ensure the integrity and scalability of the entire system remain the responsibility of the engineer.

In this article, we will systematically explain everything from the timeless "First Principles" of concurrency theory to the mental models for combining them, and finally, concrete implementation patterns.

---

## 1. First Principles: Concurrency vs. Parallelism

Before learning design patterns, we must eliminate ambiguity in definitions. **Concurrency** and **Parallelism** are distinctly different.

### 1.1 Definitions and Reality

|     Concept     |                            Definition                            |   Hardware Requirement    |                        Purpose                         |
| :-------------: | :--------------------------------------------------------------: | :-----------------------: | :----------------------------------------------------: |
| **Concurrency** | Multiple tasks are in **progress** (switching via time-slicing). | Possible on a single core | Effective utilization of wait time (e.g., I/O waiting) |
| **Parallelism** |   Multiple tasks are executing **physically simultaneously**.    |    Requires multi-core    |     Improving throughput (calculation speed, etc.)     |

> **"Concurrency is about dealing with lots of things at once. Parallelism is about doing lots of things at once."**
> — Rob Pike (Co-creator of Go)

```mermaid
graph LR
    subgraph "Concurrency"
        direction TB
        A1["Task A<br/>Running"] --> A2["Task B<br/>Running"] --> A3["Task A<br/>Running"] --> A4["Task B<br/>Running"]
        style A1 fill:#e1f5fe
        style A2 fill:#fff3e0
        style A3 fill:#e1f5fe
        style A4 fill:#fff3e0
    end

    subgraph "Parallelism"
        direction TB
        B1["Core 1: Task A Running"]
        B2["Core 2: Task B Running"]
        style B1 fill:#e1f5fe
        style B2 fill:#fff3e0
    end

```

### 1.2 Two Approaches to State Management (and the Hybrid Reality)

The difficulty of concurrency lies in "managing state (memory)." Theoretically, there are two main approaches, but **in real-world systems (especially in Go, Rust, etc.), these are combined in the right places**.

#### A. Shared Memory Model

Multiple threads reference the same address space.

* **Features**: Fast because it only requires passing pointers. Suitable for simple state sharing.
* **Risks**: Exclusive control (Mutex/Lock) is mandatory to prevent Race Conditions.
* **Examples**: Java (Threads), C++ (std::thread). Go's `sync.Mutex` and Rust's `Arc/Mutex` also fall under this model.

#### B. Message Passing Model

Each process/thread has independent memory and exchanges data via communication.

* **Features**: Safe because memory is not shared. The philosophy is "Do not communicate by sharing memory; instead, share memory by communicating." Suitable for pipelining processes.
* **Risks**: Overhead from data copying occurs.
* **Examples**: Erlang (Actors). Go's `Channel` and Rust's `mpsc` also fall under this model.

> **💡 Field Best Practice**
> Even in Go, which recommends message passing, the official best practice is to use `sync.Mutex` (shared memory) for protecting internal caches (Maps) or simple counters. Modern design is not a binary choice but a proper application of both: **"Use messages for coordinating control flow, and use locks for protecting simple state."**

---

## 2. Theoretical Limits: How Fast Can It Go?

There are physical and mathematical limits to parallelization.

### 2.1 Amdahl's Law

**"The serial processing part (which cannot be parallelized) becomes the bottleneck, limiting the overall performance improvement."**

* : Parallelizable proportion (e.g., 0.9 = 90%)
* : Number of processors
* : Serial proportion (cannot be parallelized)

If **10%** of the program is serial (), even if you provide **infinite** processors (), it will only become **10 times** faster () at maximum.

### 2.2 Gustafson's Law

Amdahl's Law assumes "fixed problem size." In reality, if resources increase, we try to solve **larger problems (higher resolution, more data)**.
This theory states that under the premise of "fixed time, expanded problem size," the speedup from parallelization scales linearly with the number of processors.

Here, as the number of processors  increases, the absolute amount of the parallelizable part  expands, so the strict cap (upper limit) seen in Amdahl's Law does not occur.

---

## 3. The 4 Demons to Avoid

Concurrency bugs have low reproducibility and are difficult to debug. Structurally preventing the following 4 patterns is the main goal of design.

```mermaid
graph TB
    PROBLEMS["Pathologies of Concurrency"] --> RC["Race Condition"]
    PROBLEMS --> DL["Deadlock"]
    PROBLEMS --> LL["Livelock"]
    PROBLEMS --> ST["Starvation"]

    RC --> RC_DESC["Data integrity is destroyed<br/>due to access timing"]
    DL --> DL_DESC["Processes wait for each other's resources<br/>permanently stopping execution"]
    LL --> LL_DESC["Processes yield resources to each other<br/>state changes but no progress is made"]
    ST --> ST_DESC["Priority is too low<br/>resources never circulate to the task"]

    style RC fill:#ffcdd2,stroke:#e57373
    style DL fill:#ef9a9a,stroke:#e53935
    style LL fill:#fff59d,stroke:#fbc02d
    style ST fill:#ffcc80,stroke:#fb8c00

```

---

## 4. Mental Model: Combining 3 Layers

Before diving into concrete patterns, let's map out the design landscape.
Concurrency design patterns are **not conflicting, but rather meant to be combined across layers**.

It is easy to understand if you compare it to designing a restaurant kitchen.

|            Layer             |         Role          |        Decision to make        |
| :--------------------------: | :-------------------: | :----------------------------: |
|    **Lv 3. Architecture**    | **Overall Structure** | Data flow of the entire system |
| **Lv 2. Task Decomposition** |      **Tactics**      |   How to handle large tasks    |
|  **Lv 1. State Management**  |   **Communication**   |    Rules for data transfer     |

### Combination Decision Tree

The combination of patterns you should choose depends on what you want to build.

```mermaid
graph TD
    Start[Start Concurrency Design] --> Q1{System Objective?}
    
    Q1 -->|Calculation Heavy<br/>Maximize CPU Usage| A[Route A: Calculation/Batch]
    Q1 -->|Flow Heavy<br/>Handle Requests| B[Route B: Web/Stream Processing]

    subgraph "Route A (HPC/AI/Image Proc)"
        A --> A_L3["Lv3 Architecture<br/>Scatter-Gather"]
        A_L3 --> A_L2["Lv2 Task Decomposition<br/>Fork-Join / Work Stealing"]
        A_L2 --> A_L1["Lv1 State Management<br/>Shared Memory (Atomic/Mutex)"]
    end

    subgraph "Route B (Web API/Log Proc)"
        B --> B_L3["Lv3 Architecture<br/>Pipeline / Actor / Reactor"]
        B_L3 --> B_L2["Lv2 Task Decomposition<br/>Producer-Consumer"]
        B_L2 --> B_L1["Lv1 State Management<br/>Message Passing (Channel/Queue)"]
    end
    
    style Start fill:#f9f9f9,stroke:#333,stroke-width:2px
    style A fill:#e1bee7
    style B fill:#b3e5fc

```

From the next chapter, we will explain each element (pattern) on this map specifically.

---

## 5. Lv2 Pattern: Task Decomposition

First is the Lv2 pattern: "How to split a large job into processable sizes."

### 5.1 Fork-Join Pattern

Recursively split tasks and finally integrate the results.

* **Structure**: Split (Fork) → Execute → Wait/Combine (Join).
* **Application**: Divide and conquer algorithms like Merge Sort, Image Processing.
* **Implementation**: Java `ForkJoinPool`.

```mermaid
graph TD
    subgraph "Fork Phase (Split)"
        Root["Large Task"] -->|Split| S1["Subtask A"]
        Root -->|Split| S2["Subtask B"]
        S1 -->|Split| W1["Worker 1"]
        S1 -->|Split| W2["Worker 2"]
        S2 -->|Split| W3["Worker 3"]
        S2 -->|Split| W4["Worker 4"]
    end

    subgraph "Join Phase (Integrate)"
        W1 -->|Result| R1["Result A"]
        W2 -->|Result| R1
        W3 -->|Result| R2["Result B"]
        W4 -->|Result| R2
        R1 -->|Result| Fin["Final Result"]
        R2 -->|Result| Fin
    end

    style Root fill:#bbdefb
    style Fin fill:#c8e6c9

```

### 5.2 MapReduce Pattern

The classic and royal road of distributed processing. By separating processing into "Transform (Map)" and "Aggregate (Reduce)", dependencies between nodes are severed.

1. **Map**: Transform input into `(key, value)`. Executable in parallel.
2. **Shuffle**: Transfer data with the same `key` to the same node.
3. **Reduce**: Aggregate values for each `key`.

```mermaid
graph LR
    Input["Input Data"] --> Split

    subgraph "Map Phase (Parallel Transform)"
        Split --> M1["Map 1<br/>(dog, 1)"]
        Split --> M2["Map 2<br/>(cat, 1)"]
        Split --> M3["Map 3<br/>(dog, 1)"]
    end

    M1 & M2 & M3 --> Shuffle

    subgraph "Shuffle Phase (Transfer)"
        Shuffle["Shuffle & Sort<br/>Group by Key"]
    end

    Shuffle -->|"Key: dog"| R1
    Shuffle -->|"Key: cat"| R2

    subgraph "Reduce Phase (Aggregate)"
        R1["Reduce 1<br/>(dog, 2)"]
        R2["Reduce 2<br/>(cat, 1)"]
    end

    R1 & R2 --> Output["Final Output"]

    style Shuffle fill:#fff9c4,stroke:#fbc02d,stroke-width:2px

```

### 5.3 Work Stealing Pattern

A dynamic load balancing pattern. "Idle threads steal work from busy threads," maximizing CPU utilization.

* **Self (Owner)**: Takes tasks from the **head** of its own queue (LIFO). High cache hit rate.
* **Thief**: Steals tasks from the **tail** of others' queues (FIFO). Minimizes contention.
* **Adoption**: Go Runtime Scheduler, Java ForkJoinPool, Rust Tokio.

```mermaid
graph TD
    subgraph "Processor A (Busy)"
        Owner1((Worker A))
        Deque1[/"Task Queue (Deque)"/]
        
        T1["Task 1 (Cold)"]
        T2["Task 2"]
        T3["Task 3 (Hot)"]
        
        Deque1 --- T1
        T1 --- T2
        T2 --- T3
        
        Owner1 -->|"1. Pop (LIFO)<br/>Take own work"| T3
    end

    subgraph "Processor B (Idle)"
        Owner2((Worker B))
        Deque2[/"Empty"/]
        
        Owner2 -.->|"2. Steal (FIFO)<br/>Steal from back!"| T1
    end

    style Owner2 fill:#ffcc80,stroke:#f57c00,stroke-width:4px
    style T1 fill:#e1f5fe
    style T3 fill:#ffcdd2

```

### 5.4 Master-Worker Pattern

A centralized pattern where roles are clearly divided between the "Master" who manages processing and "Workers" who perform the actual calculations.
The Master handles task assignment, progress tracking, and retries upon failure, while Workers simply follow orders and calculate.

* **Structure**: Master manages the task queue, Workers accept (or are assigned) work from it.
* **Features**: Fault-tolerant. If a Worker dies, the Master simply re-assigns the task to another Worker.

```mermaid
graph TB
    subgraph "Control Plane (Master)"
        M["Master / Manager<br/>(Scheduling & Monitoring)"]
        Q[("Task Queue")]
    end

    M -->|"1. Assign Task"| W1["Worker Node 1"]
    M -->|"1. Assign Task"| W2["Worker Node 2"]
    
    subgraph "Data Plane (Workers)"
        W1 -->|"2. Process"| W1_Proc["Calculation"]
        W2 -->|"2. Process"| W2_Proc["Calculation"]
        
        W3["Worker Node 3<br/>(💀 Failed)"]
    end

    W1_Proc -.->|"3. Report Result"| M
    W3 -.->|"❌ No Response"| M
    M -->|"4. Re-assign (Retry)"| W2

    style M fill:#e1bee7,stroke:#8e24aa,stroke-width:2px
    style W3 fill:#cfd8dc,stroke:none,color:#90a4ae
    style Q fill:#fff9c4

```

* **🔍 Specific Use Case**: **Kubernetes / CI/CD Pipelines**
* **Kubernetes**: The **Control Plane (Master)** decides the pod schedule and issues commands to the kubelet on each **Node (Worker)**. If a Node crashes, the Master restarts the pods on another Node.
* **Jenkins / GitHub Actions**: The **Controller** manages build jobs, while **Agents (Runners)** execute the actual builds and tests.


* **Difference from Work Stealing**:
* **Master-Worker**: A "Boss (Master)" manages work. There is management cost, but overall control is effective.
* **Work Stealing**: There is no boss; "Peers" accommodate each other. It is autonomous, but grasping the overall situation is difficult.



---

## 6. Lv3 Pattern: Architecture and Data Flow

Lv3 (Macro perspective) patterns define how data flows through the entire system.

### 6.1 Pipeline Pattern

Processing is divided into stages, and each stage is connected by a queue (buffer).
It absorbs throughput differences between stages and turns the entire system into stream processing.

```mermaid
graph LR
    Source["App Logs"] -->|Push| Q1[("Kafka / Redis<br/>(Buffer)")]
    
    subgraph "Stage 1: Ingest"
        Q1 --> W1["Logstash / Fluentd<br/>(Filter & Grok)"]
    end
    
    W1 -->|Push| Q2[("Internal Queue")]
    
    subgraph "Stage 2: Index"
        Q2 --> W2["Elasticsearch<br/>(Indexing)"]
    end
    
    W2 --> Sink["Kibana<br/>(Visualize)"]

    style Q1 fill:#fff9c4,stroke:#fbc02d
    style Q2 fill:#fff9c4,stroke:#fbc02d
    style W1 fill:#bbdefb
    style W2 fill:#90caf9

```

* **🔍 Implementation Example**: **ELK Stack (Elasticsearch, Logstash, Kibana) Log Pipeline**
* **Structure**: Application logs are buffered in **Kafka**, formatted by **Logstash**, and indexed by **Elasticsearch**.
* **Effect**: Even if Elasticsearch writing is delayed, Kafka accepts the overflowing logs as a buffer, so the application side does not stop.



### 6.2 Producer-Consumer Pattern

Producers and Consumers are separated by a "Bounded Queue."
The key is control of **Backpressure**. Design decisions are needed on whether to block the producer or discard data when the queue is full.

```mermaid
graph LR
    subgraph "Producers"
        P1["Web Server A"]
        P2["Web Server B"]
    end

    P1 & P2 -->|Publish| Q{{"Amazon SQS<br/>(Visibility Timeout)"}}

    subgraph "Consumers"
        Q -->|Poll| W1["AWS Lambda<br/>(Image Resize)"]
        Q -->|Poll| W2["AWS Lambda<br/>(Image Resize)"]
    end

    Q -.->|"🛑 Evacuate to DLQ / Throttling"| P1

    style Q fill:#ffcc80,stroke:#f57c00,stroke-width:2px
    style W1 fill:#e1f5fe,stroke:#0288d1
    style W2 fill:#e1f5fe,stroke:#0288d1

```

* **🔍 Implementation Example**: **Amazon SQS + AWS Lambda (Serverless Architecture)**
* **Structure**: The Web Server (Producer) uploads an image to S3 and puts a notification in **SQS**. **Lambda** (Consumer) picks it up and creates a thumbnail.
* **Backpressure**: Even if image uploads surge, SQS acts as a cushion, adjusting the processing pace so as not to exceed Lambda's Concurrency Limit.



### 6.3 Scatter-Gather Pattern

One request is **scattered** to multiple backends, and the results are **gathered**.
Used frequently in search engines, price comparison sites, and aggregation in microservices.

```mermaid
graph TB
    Client["Client Query"] --> Node["Coordinator Node<br/>(Search Window)"]
    
    Node -->|"Scatter<br/>(Broadcast)"| S1["Shard A<br/>(Data: A-M)"]
    Node -->|"Scatter"| S2["Shard B<br/>(Data: N-Z)"]
    Node -->|"Scatter"| S3["Shard C<br/>(Replica)"]

    S1 -.->|"Gather (Top 10)"| Node
    S2 -.->|"Gather (Top 10)"| Node
    S3 -.->|"Gather (Top 10)"| Node

    Node -->|"Merge & Sort"| Response["Final Top 10"]

    style Node fill:#e1bee7,stroke:#8e24aa,stroke-width:2px
    style Response fill:#c8e6c9

```

* **🔍 Implementation Example**: **Elasticsearch (Distributed Search)**
* **Structure**: A search query from a client is received by a "Coordinator Node" and scattered to all "Shards" holding data.
* **Gather**: Each shard returns only the "Top 10 search results" within its own data, and the coordinator merges them to create the final ranking. This is why Google-scale searches finish in milliseconds.



---

## 7. Lv3/Lv1 Pattern: Async & Messaging

Patterns for minimizing I/O wait time without blocking threads. This has properties of both Architecture (Lv3) and Communication (Lv1).

### 7.1 Actor Model

**"Everything is an actor."**
Each actor has a "Mailbox" and processes messages asynchronously. The internal state of the actor is hidden from the outside, guaranteeing thread safety.

* **Merit**: Lock-free design, high location transparency (can send to actors on other servers in the same way).

```mermaid
graph LR
    subgraph "Actor A (Sender)"
        StateA[("State A")]
        LogicA["Logic"]
    end

    subgraph "Actor B (Receiver)"
        MailboxB[/"📩 Mailbox (Queue)"/]
        LogicB["Logic (Single Thread)"]
        StateB[("State B<br/>(Private)")]
        
        MailboxB -->|"Process one by one"| LogicB
        LogicB --> StateB
    end

    LogicA -.->|"Message: Update(5)"| MailboxB

    style StateB fill:#ffcc80,stroke:#f57c00
    style MailboxB fill:#e1f5fe

```

* **🔍 Representative Implementation / Adoption**:
* **Erlang/OTP & Elixir**: Chat infrastructure for **WhatsApp** and **Discord**. Handles hundreds of millions of user connections with millions of lightweight processes (actors).
* **Akka (Scala/Java)**: Framework for building distributed systems. Similar concepts are used behind FaaS like AWS Lambda.
* **Microsoft Orleans**: Adopted on the server side of the game **"Halo 4"**. Uses the concept of "Virtual Actors" to automatically move actors to other servers during server failure.



### 7.2 CSP (Communicating Sequential Processes)

A model adopted by the Go language. While the Actor Model emphasizes "Who to send to (ID)," CSP emphasizes "Where to send (Channel)." Processes and channels become loosely coupled, allowing for flexible configuration.

```mermaid
graph LR
    subgraph "Process 1 (Goroutine)"
        Code1["Process A"]
    end

    subgraph "Channel (Pipe)"
        Chan{{"Channel<br/>(Buffer)"}}
    end

    subgraph "Process 2 (Goroutine)"
        Code2["Process B"]
    end

    Code1 -->|"Send"| Chan
    Chan -->|"Receive"| Code2

    style Chan fill:#c8e6c9,stroke:#43a047,stroke-width:2px

```

* **🔍 Representative Implementation / Adoption**:
* **Go (Goroutines & Channels)**: Native support as a language feature. Heavily used in the internal implementation of Docker and Kubernetes.
* **Clojure (core.async)**: Library realizing CSP on the JVM.
* **Kotlin (Coroutines Channel)**: Realizes behavior close to Go channels in Kotlin.



### 7.3 Future / Promise

An abstraction for handling the results of asynchronous processing.

* **Future**: "A read-only placeholder where a value is scheduled to enter in the future."
* **Promise**: "A write port to enter the value after calculation is complete."
* **Modern**: Recent languages (JS, Rust, C#, etc.) allow writing asynchronous processing serially using `async/await` syntax, but this pattern is running behind the scenes.

```mermaid
sequenceDiagram
    participant Main as Main Thread
    participant Async as Async Task
    participant Future as Future Object
    
    Main->>Async: 1. Start Process (Start)
    Async-->>Main: 2. Return "Box" immediately (Return Future)
    Note over Main: (Main does other work)
    
    Async->>Async: 3. Heavy Calculation...
    Async->>Future: 4. Put value in Box (Resolve/Complete)
    
    Main->>Future: 5. Open Box (await / .get())
    Future-->>Main: 6. Get Value (Value)

```

* **🔍 Representative Implementation / Adoption**:
* **JavaScript (Promise / async-await)**: Basis of Web Frontend development like `fetch('api')`.
* **Java (CompletableFuture)**: Describes chains of asynchronous tasks (After A, then B, then C).
* **Rust (Future trait)**: Combined with runtimes like `Tokio` to realize zero-cost abstracted asynchronous processing.



### 7.4 Reactor / Proactor Pattern

Event-driven architecture for handling massive concurrent connections (C10K problem).

* **Reactor (Node.js, Netty)**: Notifies that "Reading is **possible**." The application performs the reading process itself.
* **Proactor (Windows IOCP, tokio-uring)**: Notifies that "Reading is **completed**." The OS performs I/O on behalf (True Asynchronous I/O).

```mermaid
graph TD
    subgraph "Event Loop (Single Thread)"
        Loop((Loop))
        Select["I/O Multiplexer<br/>(epoll / kqueue)"]
        Handler["Event Handler<br/>(Callback)"]
    end

    Clients["Clients (10,000+)"] --"Connections"--> Select
    Select --"1. Ready Event<br/>(Readable!)"--> Loop
    Loop --"2. Dispatch"--> Handler
    Handler --"3. Non-blocking Read"--> Select

    style Loop fill:#ffeb3b,stroke:#fbc02d
    style Select fill:#e0e0e0

```

* **🔍 Representative Implementation / Adoption**:
* **Node.js (libuv)**: Representative for handling massive I/O with a single thread. Based on the Reactor pattern.
* **Nginx**: Achieved overwhelming simultaneous connection numbers compared to Apache (Thread Model) by combining "Master-Worker Model" x "epoll (Reactor)".
* **Netty (Java)**: Java asynchronous network framework. Runs behind Spring WebFlux and gRPC.
* **io_uring (Linux)**: Latest Linux kernel feature. Realizes high-speed I/O of "Completion Notification" type close to Proactor pattern, being adopted in next-generation DBs and Web servers.



> **💡 Column: What is the difference from CSP (Channel)?**
> The goal of "Non-blocking" is the same, but the **Layer** they solve is different.
> * **Reactor (epoll)**: **OS Level**. Interested in the **Notification** of "**When** can I read?"
> * **CSP (Channel)**: **App Level**. Interested in the **Coordination** of "**What** to send to whom?"
> 
> 
> In fact, behind the runtimes of Go (CSP) and Node.js (Event Loop), this Reactor pattern runs mud-stained like an engine, supporting the concurrency models that are easy for humans to handle.

---

## 8. Case Studies: Standing on the Shoulders of Giants

Let's see how these Lv1-Lv3 patterns are combined in systems that actually support the world.

### Case 1: Nginx (Champion of C10K)

Nginx, the de facto standard for Web servers, was designed to solve the problem that "Creating massive threads is heavy."

* **Lv3 Architecture**: **Event-Driven (Reactor)**
* Runs with one master process and a few worker processes.


* **Lv1 State Management**: **Non-blocking I/O**
* Does not stop threads waiting for requests, but switches processing only by notification from the OS (epoll/kqueue).


* **Effect of Combination**:
* Minimized memory consumption and made it possible to handle tens of thousands of simultaneous connections. Node.js also follows this architecture.



### Case 2: Go Runtime Scheduler (Demon of CPU Efficiency)

The secret to "Why can Go run millions of Goroutines?" lies in the task decomposition of the runtime itself.

* **Lv3 Architecture**: **M:N Threading**
* Maps OS threads (M) and lightweight Goroutines (N) in a many-to-many relationship.


* **Lv2 Task Decomposition**: **Work Stealing**
* When a processor's queue becomes empty, it steals half of the Goroutines from another busy processor's queue.


* **Lv1 State Management**: **CSP (Channels) & Mutex**
* While recommending channels at the user code level, it uses fast atomic operations/Mutex for queue operations and memory management inside the runtime.


* **Effect of Combination**:
* Automatically uses the performance of multi-core CPUs while avoiding heavy OS context switches.



### Case 3: Chromium / Modern Browsers (Keystone of Robustness)

"Even if one tab crashes, the entire browser does not go down." This norm is a victory of concurrency patterns.

* **Lv3 Architecture**: **Multi-Process Architecture**
* Assigns an independent process (Renderer Process) to each tab. This is a concept close to the Actor Model in a broad sense.


* **Lv1 State Management**: **Message Passing (IPC)**
* Memory is not shared between processes; they communicate via IPC (Inter-Process Communication).


* **Effect of Combination**:
* Even if a memory protection violation occurs, the impact can be confined only to that tab (process).



---

## Conclusion

Concurrency design patterns are not just code fragments.
They are **blueprints for appropriately combining the three layers of "Architecture," "Task Decomposition," and "State Management" according to the purpose**.

Even when using code generated by AI, humans must perform reviews from the following perspectives:

1. **Validity of Selection**: Are you using "Actor Model" even though it is "Calculation Heavy"? (Excessive overhead)
2. **Layer Consistency**: Are you using inappropriate shared memory locks (Lv1) inside a Pipeline (Lv3)?
3. **Understanding Constraints**: Are you over-parallelizing while ignoring Amdahl's Law?

Only by having this "basic fitness" and "overview" and leveraging AI tools will it be possible to build robust and scalable systems of the 2026 standard.

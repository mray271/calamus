# Mermaid Math Examples (KaTeX v10.9.0+)

Mermaid supports mathematical expressions through the [KaTeX](https://katex.org/)
typesetter (Mermaid v10.9.0+).  The `$$...$$` delimiter is used inside diagram
node labels, edge labels, and sequence participants.

Reference: https://mermaid.js.org/config/math.html

---

## Flowchart with Math Nodes and Edge Labels

```mermaid
graph LR
    A["$$x^2$$"] -->|"$$\sqrt{x+3}$$"| B("$$\frac{1}{2}$$")
    A -->|"$$\overbrace{a+b+c}^{\text{note}}$$"| C("$$\pi r^2$$")
    B --> D("$$x = \begin{cases} a &\text{if } b \\ c &\text{if } d \end{cases}$$")
    C --> E("$$x(t)=c_1\begin{bmatrix}-\cos{t}+\sin{t}\\ 2\cos{t} \end{bmatrix}e^{2t}$$")
```

## Sequence Diagram with Math Participants and Messages

```mermaid
sequenceDiagram
    autonumber
    participant 1 as $$\alpha$$
    participant 2 as $$\beta$$
    1->>2: Solve: $$\sqrt{2+2}$$
    2-->>1: Answer: $$2$$
    Note right of 2: $$\sqrt{2+2}=\sqrt{4}=2$$
```

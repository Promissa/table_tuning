# Research Plan: Table Parsing Dataset

## Benchmark

### TEDS

内容完整性评估，有现成的 module，类似于之前实现的二维 levenshtein

### GriTS

$$
\text{GridTS}_f(\mathbf A,\mathbf B) =\frac{2\sum_{i,j}f(\text{2D-MSS}_f(\mathbf{A,B}))}{|\mathbf{A}|+|\mathbf{B}|}
$$

where

$$
\text{2D-MSS}_f(\mathbf{A,B})=\arg\max_{A'|A,B'|B}\sum_{i,j}f(\mathbf{A}'_{i,j},\mathbf{B}'_{i,j}), f\in[0,1]
$$

where $\bf A',B'$ are 2D-subsequences of two matrices $\bf A,B$.

## Size

3K 左右，主要 focus 在 Form 10-K,20-F,10-Q，可另外处理 Form S-1,S-3

##

# `STRATA_IO_PF_STAGE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

Linux の mapped file tier で `STRATA_IO_PREFETCH` が有効なとき、未キャッシュの expert を worker が scratch buffer に読み込んで OS page cache を温める既定動作を、expert ごとの staging buffer へ読み込む動作に切り替える。staging された expert はファイル mapping ではなく staging buffer から供給され、現在層の必要な expert の読み込みが終わるまでその層の処理が待つことがある。対象は主に pack の `experts.bin` 経路である。

## 値と判定

値は文字列全体として比較せず、C/C++ の `std::atoi` で整数に変換し、結果が 0 以外なら staging を選ぶ。

| 値 | 判定 |
|---|---|
| 未設定 | 0 と同じ。staging は選ばず、`experts.bin` では page cache を埋める既定方式 |
| 空文字、数字で始まらない文字列、`0`、`0tail` | `atoi` の結果が 0。staging しない |
| `1`、`-1`、`2tail` など、変換結果が 0 以外 | staging を選ぶ |

`atoi` は先頭の空白と符号を許し、先頭の10進整数部分を変換するため、`  +1tail` も有効、`  -0x` は 0 となる。全体の構文検証や値域 clamp はない。変換結果が `int` に収まらない文字列の挙動はこの実装から保証できない。根拠: `src/core/expert_source.cpp:659-662`。

## 有効になる条件

- `strata generate` が `STRATA_IO_PREFETCH` を設定済みかつ `atoi(value) != 0` と判定し、`FileExpertSource::set_io_prefetch(true, ...)` を呼ぶ必要がある。I/O prefetch 自体は Linux で mapped file tier を使い、unbuffered reader ではない場合に限り開始する。使えない場合は `STRATA_IO_PREFETCH=1 is not available here ...` と出て、設定値は適用されない（`src/program/generate.cpp:4667-4678`; `src/core/expert_source.cpp:636-640,667-669`）。
- `set_io_prefetch` は Linux 以外では I/O prefetch を開始しない。Linux でも mapping がない、パスが空、または direct reader がある場合は、設定を読む前に戻る（`src/core/expert_source.cpp:636-640`）。
- `experts.bin` では `role_ptr_` が空なので、この値が staging と page-cache fill の切り替えになる。GGUF shard を直接 mapping する経路では `role_ptr_` が空でなく、`io_fill_` は値に関係なく false になるため、この変数による切り替えはない（`src/core/expert_source.cpp:659-662,1112-1115`）。
- どちらの方式も router-aware lookahead が必ず成立することを意味しない。次層の予測読み込みは `STRATA_LOOKAHEAD` の条件、ルーター重みの形式、予測器の起動成功に依存する（`src/program/generate.cpp:5496-5523`）。

## 実行時の詳細

値は file tier の初期化時、`STRATA_IO_PREFETCH` によって `set_io_prefetch` が呼ばれるたびに一度読み込まれ、`io_fill_` に保存される。static cache ではないが、同じ `FileExpertSource` が起動後にこの値を読み直す経路は確認できない。したがって実用上は初期化前に設定する。

既定の `experts.bin` page-cache fill では、worker が uncached な blob を scratch buffer に `pread` し、データを page cache に置く。compute 側は mapping を使う。非0値では worker が uncached blob を staging buffer に読み、需要層は `prefetch` で対象 expert をまとめて stage し、worker に先読みを渡した場合は `io_blob` が staged blob を返す。page cache にある blob は mapping から返る。`STRATA_IO_PF_AHEAD=0` は予測先読みを止める別設定であり、`STRATA_IO_PF_STAGE` が非0でも demand read の staging 経路は残る（`src/core/expert_source.cpp:702-770,777-803,1426-1484`; `src/core/expert_source.cpp:2137`）。

`STRATA_IO_PREFETCH` が有効で、この変数も `atoi` で非0のとき、起動時に次の案内が stderr に出る。これは推奨の測定注記であり、処理を強制・抑止しない。

```text
strata generate: note: STRATA_IO_PF_STAGE=1 (staging) measured faster only on a 32 GB-class box (+25% on an RTX 3060, 32 GB); it was slower at 16 GB and on an iGPU (docs/DETAILS.md, file tier I/O)
```

Strata の `docs/DETAILS.md:225-245` は staging mode が未キャッシュ expert を buffer に読み、層がそれを待つと説明する。記載された測定条件は、interleaved A/B 10 組、200-token greedy median、各 run 前の page cache drop、cgroup memory limit。RTX 3060 32 GB / IQ3_XXS では default -3.4%、staging +25.7%、RTX 3060 16 GB / IQ3_XXS では -1.8% / -32.6%、Radeon 780M iGPU 16 GB / Q2_0 では -0.7% / -19%（この iGPU の測定は adaptive tier off）。これは記載条件での結果であり、他環境の性能を示すものではない。ソースには iGPU で適応層と I/O prefetch を併用した際の GPU reset 警告もあるが、原因は未特定と docs は述べている（`src/program/generate.cpp:4680-4691`）。

## 根拠

- `src/program/generate.cpp:4667-4683` — I/O prefetch の起動条件、利用可否ログ、staging 測定注記。
- `src/core/expert_source.cpp:636-669` — Linux 限定の初期化、変数の parse、`io_fill_` の決定。
- `src/core/expert_source.cpp:702-770,777-803,1426-1484` — worker の cache fill / staging、blob の供給、需要層の prefetch。
- `src/program/generate.cpp:5496-5523` — lookahead の成立条件。
- `docs/DETAILS.md:225-245` — 設計説明、記録された測定条件と値。

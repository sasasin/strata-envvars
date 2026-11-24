# `STRATA_INK_Q8_0_DENSE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

CUDA 対応 `strata-inkling` が条件を満たす単一 GPU を使う場合、GGUF の Q8_0 dense 行列を読み込み時に BF16 へ展開せず、Q8_0 のまま保持するかを切り替える。保持すると attention の Q/K/V/R/gate/output 行列と特定形状の embedding が Q8_0 形式で格納され、CUDA runner は該当する attention projection に Q8F GEMM 経路を使う。値が `0` で始まると保持を無効化し、loader は BF16 へ展開する。環境変数による有効化は `engine/src/inkling2/ink_main.cpp:1030-1037`、GGUF dense 行列の選択と BF16 fallback は `engine/src/inkling2/ink_gguf_loader.h:497-535`、runner の Q8F 経路は `engine/src/inkling2/cuda/ink_runner.cuh:2861-2910,3195-3214`。

これは `strata-inkling` の GGUF loader に対する切り替えであり、一般の Strata backend 設定ではない。CUDA 以外、CPU、または以下の GPU 条件を満たさない経路では、この環境変数を読み取らず、Q8_0 dense 行列は既定の BF16 展開経路になる。`.strata` / safetensors 形式の loader に対するこの変数の効果は確認できない（`engine/src/inkling2/ink_main.cpp:1030-1037`; GGUF の呼び出し箇所 `engine/src/inkling2/ink_gguf_loader.h:574-579,625-636`）。

## 値と判定

CUDA 対応ビルドで実行時に条件を満たしたときだけ `std::getenv` を呼び、その文字列の先頭 1 文字を `'0'` と比較する。数値や真偽値として parse せず、文字列全体も検査しない。未設定および空文字は保持を有効にし、先頭が `0` の文字列は残りに関係なく無効にする（`engine/src/inkling2/ink_main.cpp:1030-1036`）。

| 条件 | unset | 保持が有効になる値の例 | 保持が無効になる値の例 |
|---|---|---|---|
| CUDA ビルド、`--cpu` なし、GPU 1 台、layer split なし、選択 GPU が `sm_86` | 有効 | 空文字、`1`、`true`、`false`、` 0`、`off` | `0`、`0anything` |
| 上記以外（CUDA 以外のビルドを含む） | 無効（BF16 展開） | 該当なし。この分岐では値を読まない | 該当なし |

`false` や `off` も先頭が `0` ではないため、このコード上は保持を有効にする。大文字小文字・空白・数値としての妥当性は検査されない。`sm_86` 以外の GPU では、環境変数を `1` にしてもこの分岐に入らない（`engine/src/inkling2/cuda/ink_cuda_backend.cu:1239-1250`）。

## 有効になる条件

- `INKLING_ENABLE_CUDA` が定義されたビルドであること。環境変数判定自体がこの compile-time guard 内にある（`engine/src/inkling2/ink_main.cpp:1030-1037`）。
- `--cpu` が指定されず、`cfg.bopts.gpus == 1`、`cfg.bopts.layer_split.empty()`、選択 GPU が `sm_86` であること。対応判定は CUDA の device 属性を読み、major が 8 かつ minor が 6 の場合だけ true を返す。属性取得失敗時も false となる（`engine/src/inkling2/ink_main.cpp:1033`; `engine/src/inkling2/cuda/ink_cuda_backend.cu:1239-1250`）。
- GPU 数は CLI の `--gpus` / `--devices` で決まり、初期値が 1 台相当で GPU ID が未指定なら `IK2_GPUS` が上書きできる。このため `IK2_GPUS` が複数台を指定すると対象分岐に入らない（`engine/src/inkling2/ink_main.cpp:920-944,996-1018`）。`--cpu` と `--layer-split` も対象分岐から外す（同 `:945-952,1033-1035`）。
- 上記条件を満たして保持が有効でも、効果があるのは GGUF loader が処理する Q8_0 dense tensor だけ。`copy_mat_dense` は tensor type が Q8_0、列数が 32 の倍数、行列要素数が 256 の倍数であることを要求し、attention 用 fragment layout では行数が 16 の倍数であることも要求する。条件に合わない tensor は同じ helper 内で BF16 へ展開する（`engine/src/inkling2/ink_gguf_loader.h:502-507`）。Embedding は `vocab_padded == 201024` の場合だけこの helper に渡る（同 `:572-579`）。
- 値の判定はモデルを開く前に行われるため、GGUF の読み込み時に保持／展開が決まる。`.strata` / safetensors のロードや、環境変数分岐後に個別 helper を呼ぶだけの処理ではこの切り替えは確認できない（`engine/src/inkling2/ink_main.cpp:1033-1037,1078-1087`; `engine/src/inkling2/ink_gguf_loader.h:497-535`）。

## 実行時の詳細

`main` は引数処理と `IK2_GPUS` の反映後、各種 info / selfcheck / bench / serve 経路へ分岐する前に CUDA 条件を調べる。条件を満たすと環境値を読み、関数内 static の `keep_q8_0_dense()` を設定する。同 static の初期値は false で、条件を満たさないと代入されない（`engine/src/inkling2/ink_main.cpp:991-1037`; `engine/src/inkling2/ink_gguf_loader.h:38-46`）。このため、対象条件に入らない経路では `getenv` を呼ばず既定値 false のまま。プロセス実行中に外部から環境値を変更した場合に再読込する経路はない。

GGUF の embedding と各 attention dense projection は、保持フラグが true の場合に元 tensor を参照する。適合する Q8_0 tensor は embedding 用 fmt 104、attention 用 fragment fmt 105 として loader の trunk に格納される。false、または tensor の型・形状が条件外なら BF16 へ変換する（`engine/src/inkling2/ink_gguf_loader.h:497-535,572-579,625-636`）。CUDA runner は fmt 105 の行列で、batch と列数など `q8f_ok` 条件を満たすとき Q8F GEMM を呼ぶ。満たさない場合の周辺経路も含め、保持フラグが直接変えるのは loader 上の行列形式であり、生成 token や選択結果を変える設定だとはコードから確認できない（`engine/src/inkling2/cuda/ink_runner.cuh:2861-2910,3006-3010,3195-3214`）。

## ログと測定値

この環境変数の読み取りや有効化・無効化を知らせるログは分岐内にない（`engine/src/inkling2/ink_main.cpp:1030-1037`）。条件外の GPU / backend、または tensor の形式・形状が条件外の場合は BF16 経路へ進むが、この変数を理由とする警告やエラーは確認できない（`engine/src/inkling2/cuda/ink_cuda_backend.cu:1239-1250`; `engine/src/inkling2/ink_gguf_loader.h:502-507`）。

`docs/SETTINGS.md:406` は候補一覧で「NVIDIA and AMD」と記載するが、実装で環境変数を読む箇所は `INKLING_ENABLE_CUDA` の下だけで、GPU 条件も `sm_86` のみである（`engine/src/inkling2/ink_main.cpp:1030-1037`; `engine/src/inkling2/cuda/ink_cuda_backend.cu:1239-1250`）。同じ資料の一般的な backend 表記は、この実装条件の根拠にはならない。`docs/DETAILS.md` には本変数の具体的な値規則・有効条件・測定値の説明を確認できなかったため、性能値は記載しない。

## 根拠

- 環境変数の読み取り・判定と CUDA compile guard: `engine/src/inkling2/ink_main.cpp:1030-1037`
- GPU 対応判定: `engine/src/inkling2/cuda/ink_cuda_backend.cu:1239-1250`
- 状態変数の初期値、GGUF tensor の保持と BF16 fallback: `engine/src/inkling2/ink_gguf_loader.h:38-46,497-535`
- helper に渡す embedding / attention tensor: `engine/src/inkling2/ink_gguf_loader.h:572-579,625-636`
- CUDA runner の Q8F 実行条件と呼び出し: `engine/src/inkling2/cuda/ink_runner.cuh:2861-2910,3195-3214`
- 候補一覧の記載: `docs/SETTINGS.md:406`

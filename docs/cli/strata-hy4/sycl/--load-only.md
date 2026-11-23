# `strata-hy4-sycl --load-only`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（SYCL の単発実行経路） |
| オプション | `--load-only` |
| 別名 | なし |
| 値 | 取らないフラグ。指定すると真になる |

## 役割

SYCL の単発実行経路でモデルと実行環境の初期化を行い、トークン入力を読んで推論する直前に正常終了する。モデルのロードや実行資源の準備が通るかを確認する用途に使える。`--serve` 経路ではサーバー初期化へ分岐するため、このフラグによる早期終了は行われない。

## 使い方

```sh
strata-hy4-sycl --model ./model.strata --load-only
```

`--tokens` は不要。この経路ではトークンファイルを開かない。

## 値と既定値

- 値を取らず、指定時に `load_only = true` とする。初期値は `false`。同じフラグを複数回指定しても真を再設定するだけで、値の検証や追加動作はない（`engine/src/hy4flash/sycl/sy_main.cpp:99,105-115,165`）。
- `--model` / `--native` でモデルファイルを指定しない場合、`--load-only` の有無にかかわらず usage を stderr に表示して終了コード 2 で終了する（`engine/src/hy4flash/sycl/sy_main.cpp:130,250-254`）。

## 実行時の動作

通常の単発実行経路では、フラグがなければモデルを読み込んだ後に `--tokens` のファイルを読み、空なら `no tokens` を出して終了コード 2 となる。フラグがあればこの読み込みと空入力判定を飛ばし、トークン数 0 のまま後続の初期化へ進む（`engine/src/hy4flash/sycl/sy_main.cpp:260-275`）。

フラグがあってもモデル本体のロード、Runner 初期化、expert pool の準備は省略されない。モデルロード失敗は `load: ...` と終了コード 1、Runner 初期化失敗は `init: ...` と終了コード 1、expert pool の準備失敗は `experts: ...` と終了コード 1 になる（`engine/src/hy4flash/sycl/sy_main.cpp:255-265,283-307`）。Runner は KV cache や各種 GPU buffer を確保し、Engram メタデータを読み込む。`--engram` が空でなければ Engram ファイルも開く（`engine/src/hy4flash/sycl/sy_graph.h:489-510,535-589`）。expert pool の準備では VRAM expert cache と CPU expert pool を構成する（`engine/src/hy4flash/sycl/sy_graph.h:123-159,162-235`）。

`--draft dfly2` を同時に指定すると、早期終了前に DFly2 drafter も初期化する。モデルに drafter tensor がない場合は `dfly2: this .strata has no DFly2 drafter tensors` を stderr に出し、終了コード 1 となる（`engine/src/hy4flash/sycl/sy_main.cpp:310-319`; `engine/src/hy4flash/sycl/sy_dfly2.h:511-515`）。初期化が成功すると `load_only` の分岐で終了コード 0 を返し、prefill・生成・出力ファイル作成へ進まない（`engine/src/hy4flash/sycl/sy_main.cpp:319-324,338-364`）。

## 適用条件と副作用

- 対象は `strata-hy4-sycl` の単発実行経路。`--serve` は parser 後に `hy4s_serve_main()` へ分岐して戻るため、`--load-only` はサーバー経路を停止しない（`engine/src/hy4flash/sycl/sy_main.cpp:105-107,129-130,215-249`）。
- 単発経路では GPU runtime/device を初期化し、モデル tensor、KV cache、各種作業 buffer、expert pool などを確保する。したがって、生成をしない場合でも GPU メモリとホストメモリを使う（`engine/src/hy4flash/sycl/sy_main.cpp:255-259,260-265,283-307`; `engine/src/hy4flash/sycl/sy_graph.h:489-510,535-584`）。
- `--gpu-experts` のサイズが正なら、トークン数にかかわらず `load_only` によって VRAM reserve の計算対象になる。一方、実際の `GpuExperts` 初期化は早期 return より後なので、このフラグだけでは GPU expert cache を作らない（`engine/src/hy4flash/sycl/sy_main.cpp:301-319,323-337`）。
- expert pool 準備中、Windows 以外ではモデルファイルに `POSIX_FADV_DONTNEED` を指定して stale file page cache の破棄を試みる。失敗は無視される（`engine/src/hy4flash/sycl/sy_graph.h:204-212`）。
- SYCL 例外は `SYCL exception: ...` を stderr に出して終了コード 4 となる（`engine/src/hy4flash/sycl/sy_main.cpp:612-615`）。

## 出力とエラー

初期化成功時に `--load-only` 自体が出す専用メッセージはなく、正常終了コードは 0。device 情報・Runner と expert pool の初期化状況など、実行した初期化処理の診断は stderr に出る（`engine/src/hy4flash/sycl/sy_main.cpp:255-259,301-307,319`; `engine/src/hy4flash/sycl/sy_graph.h:229-235,628-631`）。失敗時のエラーと終了コードは上記の各初期化経路に従う。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:99,105-115,165` — フラグの初期値、引数 parser、値を取らない登録。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-254` — `--serve` の別経路と単発実行でのモデル必須条件。
- `engine/src/hy4flash/sycl/sy_main.cpp:255-319` — モデル・token・Runner・expert pool・drafter の初期化順序と早期終了。
- `engine/src/hy4flash/sycl/sy_main.cpp:320-337,338-364` — 早期終了後の prefill / GPU expert setup / 推論処理。
- `engine/src/hy4flash/sycl/sy_graph.h:123-159,162-235` — expert cache・CPU expert pool の準備、ファイル page cache への処理、診断出力。
- `engine/src/hy4flash/sycl/sy_graph.h:489-510,535-589,628-631` — Runner の GPU buffer・KV cache・Engram 初期化と出力。
- `engine/src/hy4flash/sycl/sy_dfly2.h:511-515` — DFly2 tensor がない場合の初期化失敗。

調査範囲は当該 checkout の Strata 所有 SYCL ソース。実バイナリの `--help` は実行しておらず、外部 SYCL runtime / device driver の内部挙動や初期化後の物理メモリ解放タイミングは確認していない。

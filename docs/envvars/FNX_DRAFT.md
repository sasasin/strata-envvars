# `FNX_DRAFT`

調査対象: Strata `main` の HEAD `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

## 役割

`strata-split-N` の server 実行で使う drafter を選びます。既定の `mtp` は MTP draft layer を読み込み、`dflash2` は DFlash2 drafter を読み込みます。この変数自体は通常の Strata engine や他の実行ファイルでは読まれません。対象の `sfnx` は `STRATA_BUILD_SPLIT=ON` で追加される Linux CUDA/HIP 向け split engine の実行ファイルです。`src/split/CMakeLists.txt:1-5,64-77,104-110`、`CMakeLists.txt:2997-2999`。

## 値と判定

`sfnx` は CLI 引数を解析した後、`FNX_DRAFT` を一度読みます。未設定または空文字なら既に設定された `--draft` の値（省略時は `mtp`）を保ちます。非空なら値全体をそのまま drafter 名として採用し、文字列が完全一致で `mtp` または `dflash2` でなければ起動を拒否します。空白除去、大文字小文字変換、部分一致、数値変換は行いません。`src/split/tools/sfnx.cpp:65-68,73-87,103-105`。

| `FNX_DRAFT` | 選択結果 |
|---|---|
| 未設定 | `--draft` の値。`--draft` も省略なら `mtp` |
| 空文字 | 同上。空文字は環境変数による上書きとして扱わない |
| `mtp` | MTP draft layer |
| `dflash2` | DFlash2 drafter |
| その他の非空文字列（例: `MTP`, ` dflash2`, `1`） | 無効。`--draft takes mtp or dflash2` で起動を拒否 |

非空の `FNX_DRAFT` は `--draft` より優先します。たとえば `--draft mtp` と `FNX_DRAFT=dflash2` の組み合わせでは `dflash2` が選ばれます。逆に、`FNX_DRAFT` が未設定または空文字なら `--draft` が有効です。`--draft` の重複指定は解析順で後の値が残りますが、その後の非空 `FNX_DRAFT` がさらに上書きします。`src/split/tools/sfnx.cpp:73-87,103-105`。

## 有効になる条件

- `strata-split-N` がビルドされ、`sfnx` が `--serve` で起動されている必要があります。通常ビルドでは `STRATA_BUILD_SPLIT` は既定 OFF です。Split engine の CMake 条件は Linux CUDA または HIP で、対象ソースに `sfnx.cpp` を含めます。`CMakeLists.txt:2997-2999`、`src/split/CMakeLists.txt:1-5,20-30,64-77,104-110`。
- `FNX_DRAFT=dflash2` の場合、`--native`、`--draft-model PACK` と、`--draft-vocab FILE` または `--mtp DIR` の指定が必要です。`--draft-vocab` を省略して `--mtp DIR` を使うと、語彙ファイルは `DIR/draft_vocab.bin` として扱われます。この分岐では MTP layer はロードされず、DFlash2 が drafter になります。`src/split/tools/sfnx.cpp:106-110,1119-1129`。
- `FNX_DRAFT=mtp` の場合は `--native` と `--mtp DIR` が必要です。DFlash2 用の `--draft-model` はこの選択では使われません。`src/split/tools/sfnx.cpp:106-110,1120-1129`。
- 変数は drafter の選択だけを行います。対応するモデル・語彙・pack が正常にロードできなければ drafter の起動は完了しません。DFlash2 選択時は語彙ファイルの読み込み、空でないこと、token ID がモデル語彙の範囲内であること、モデルの `output.weight` が Q8_0 であることなども検査されます。`src/split/tools/sfnx.cpp:1057-1087`。

## 実行時の詳細

読み取りは `parse_args()` 中、`--serve` の検証と CLI 解析の後、モデルをロードする前に一度行われます。static cache はなく、このプロセスの起動時に決まった選択がそのサーバープロセスのモデル初期化に使われます。起動後の環境変更を再評価するコードはありません。`src/split/tools/sfnx.cpp:73-113,1103-1129`。

無効な非空値、`--serve` の欠落、選択した drafter に必要な引数の欠落は `sfnx: <理由>` を stderr に出し、終了コード 2 で終了します。DFlash2 の語彙やモデル検証、pack/デバイス初期化などモデルロード中に失敗した場合は、`ERR <理由>` を stdout と `sfnx: failed: <理由>` を stderr に出して終了コード 1 で終了します。正常な DFlash2 初期化では、stderr に `sfnx: DFlash2 on card 0: ...` の行が出ます。`src/split/tools/sfnx.cpp:105-110,1060-1087,1090-1098,1103-1131`。

## 根拠

- 候補一覧には `FNX_DRAFT` が載っています（`docs/envvars/000_envvers.md:539`）。ソース全体で名前を検索した結果、環境から値を読む実装は `src/split/tools/sfnx.cpp:104` のみです。ほかの名前一致はコメントや設計資料であり、追加の読み取り経路ではありません。
- CLI 既定値、解析、環境変数の優先順位、許容値、必須引数: `src/split/tools/sfnx.cpp:65-110`。
- drafter ごとのロードと DFlash2 の初期化ログ: `src/split/tools/sfnx.cpp:1057-1087,1119-1129`。
- split engine の build 条件と対象ソース: `CMakeLists.txt:2997-2999`、`src/split/CMakeLists.txt:1-5,20-30,64-77,104-110`。

# `--draft`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-split` |
| コマンド | `strata-split-N`（N = 2 / 3 / 4）、server 起動時 |
| オプション | `--draft` |
| 別名 | なし |
| 値 | `mtp` または `dflash2` |

## 役割

server 起動時に、split engine が生成候補を提案する drafter を選びます。既定の `mtp` は MTP draft layer を使い、`dflash2` は DFlash2 drafter を使います。`strata-split-N` は `engine/src/split/tools/sfnx.cpp` を含む実行ファイルとしてビルドされます（`engine/src/split/CMakeLists.txt:116-126`）。

## 使い方

```sh
# MTP を選ぶ（--draft 省略時と同じ。--native と --mtp は必要）
strata-split-2 --serve --native MODEL.gguf --mtp MTP_DIR --draft mtp

# DFlash2 を選び、語彙ファイルと runtime pack を指定する
strata-split-2 --serve --native MODEL.gguf --draft dflash2 \
  --draft-model DFLASH2.pack --draft-vocab VOCAB.bin
```

## 値と既定値

- `--draft` は次の引数を値として読み、既定値は `mtp` です。`--draft` を複数回指定した場合は解析順で最後に指定した値が残ります（`engine/src/split/tools/sfnx.cpp:65-68,73-87`）。
- 引数解析後、環境変数 `FNX_DRAFT` が設定されていて空でなければ、その値が `--draft` の値を上書きします。未設定または空文字なら CLI 値（省略時は `mtp`）が使われます。最終値は大文字小文字を区別して `mtp` または `dflash2` と完全一致する必要があります（`engine/src/split/tools/sfnx.cpp:103-109`）。詳しくは [`FNX_DRAFT`](../../../envvars/FNX_DRAFT.md) を参照してください。
- 値を省略すると「`--draft needs a value`」相当の parser エラーになります。未対応値は `--draft takes mtp or dflash2` で拒否されます（`engine/src/split/tools/sfnx.cpp:77-81,108-109`）。

## 実行時の動作

最終値が `mtp` の場合、`--native` で指定したモデルと `--mtp DIR` の MTP layer を読み込み、engine に MTP drafter を接続します。この選択では `--native` と `--mtp` が必要です（`engine/src/split/tools/sfnx.cpp:110-115,1119-1133`）。

最終値が `dflash2` の場合、`--native`、`--draft-model PACK` と、`--draft-vocab FILE` または `--mtp DIR` の指定が必要です。後者だけを指定した場合、語彙ファイルのパスは `DIR/draft_vocab.bin` として補われます。DFlash2 の pack はモデル・語彙情報とともに読み込まれ、MTP の代わりに DFlash2 drafter が engine に接続されます（`engine/src/split/tools/sfnx.cpp:110-114,1059-1091,1119-1133`）。

DFlash2 の語彙ファイルは 4 byte ごとの token ID として読み込まれ、空ファイルとモデル語彙の範囲外の ID は拒否されます。またモデルの `output.weight` が Q8_0 であることを要求し、pack のロードが成功すると使用カード・語彙数・drafter 数・VRAM量を stderr に出します（`engine/src/split/tools/sfnx.cpp:1061-1091`）。

## 適用条件と副作用

- `--serve` を付けた `sfnx` の起動時だけ有効です。`--serve` がなければ parser が拒否します（`engine/src/split/tools/sfnx.cpp:73-82,107`）。
- `strata-split-N` 自体は `STRATA_BUILD_SPLIT=ON` の opt-in build で追加され、Split engine は Linux CUDA/HIP 向けです。DFlash2 bridge は `strata_kernels` と `strata_core` の CMake target がある場合に組み込まれます（`engine/src/split/CMakeLists.txt:1-5,104-149`）。
- 非空の `FNX_DRAFT` が CLI 指定より優先されるため、CLI で `mtp` を指定しても環境変数が `dflash2` なら DFlash2 が選ばれます。選択はモデル初期化より前に一度行われます（`engine/src/split/tools/sfnx.cpp:103-117,1107-1129`）。
- DFlash2 は pack、モデル内の重み、語彙 ID を読み込み、カード 0 に drafter をロードします。GPU メモリを使用し、pack・モデル形式・デバイス等の初期化が失敗すれば server は起動しません（`engine/src/split/tools/sfnx.cpp:1059-1091,1117-1135`）。
- このオプションによる性能差や推奨値は、ここで参照したソースからは判断できません。

## 出力とエラー

- `--serve` 不足、無効な `--draft` 値、選択モードに必要な引数不足など、引数検証時の失敗は `sfnx: <理由>` を stderr に出し、終了コード 2 で終了します（`engine/src/split/tools/sfnx.cpp:107-117,1107-1116`）。
- モデルや drafter のロード中に失敗すると、`ERR <理由>` を stdout、`sfnx: failed: <理由>` を stderr に出して終了コード 1 で終了します（`engine/src/split/tools/sfnx.cpp:1094-1102,1123-1135`）。

## 根拠

- 索引上のツール ID、root scope、リンク: `docs/cli/000_cli_tools.md:13`、`docs/cli/README.md:1594-1603`。
- Split engine の build 条件と DFlash2 bridge の組み込み条件: `engine/src/split/CMakeLists.txt:1-5,104-149`。
- 値の既定値、parser、環境変数による上書き、値検証、モード別必須引数: `engine/src/split/tools/sfnx.cpp:65-117`。
- DFlash2 語彙とモデル重みの検証、pack のロード: `engine/src/split/tools/sfnx.cpp:1059-1091`。
- drafter のロードと engine への接続: `engine/src/split/tools/sfnx.cpp:1117-1135`。
- parser エラーとロードエラーの出力・終了コード: `engine/src/split/tools/sfnx.cpp:1094-1116`。

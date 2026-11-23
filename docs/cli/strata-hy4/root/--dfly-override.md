# `--dfly-override`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP 版、root） |
| オプション | `--dfly-override` |
| 別名 | なし |
| 値 | DFly override バイナリのファイルパス |

## 役割

モデルを GPU に読み込んだ後、指定ファイルに含まれる `model.dfly_layers.*` テンソルを、モデルの trunk 領域へ上書きする。通常実行と `--serve` の両方で使え、serve では最初のリクエスト処理より前に適用される。Metal 版は別スコープ（`strata-hy4/metal/`）であり、この文書は CUDA/HIP 版の parser と実装を扱う。

## 使い方

```sh
# DFly override を適用してロード確認後に終了する
strata-hy4 --model model.strata --dfly-override override.bin --load-only

# override を適用したモデルで serve する
strata-hy4 --model model.strata --serve --dfly-override override.bin
```

ファイル名は例示であり、override ファイルは実行環境に存在し、指定モデルの tensor manifest と互換である必要がある。

## 値と既定値

- 値は `nxt()` が受け取る次のコマンドライン引数を文字列として保持する。独自のパス形式検証や拡張子検査はない。値を省略すると stdout に `ERR --dfly-override needs a value` を出して終了コード `2` で終了する（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-384,407`）。
- 未指定時は空文字列で、override を読み込まない。値が空文字列の場合も後段の `!dfly_override.empty()` 条件を通らず、適用されない。複数回指定した場合は同じ変数へ順次代入されるため、最後の値が使われる（同 `:347,407,660-663`）。
- ファイルは `DFLYOVR1` または `DFOV0001` の magic と、1〜2048 の entry 数を持つ flat binary 形式でなければならない。両形式は entry の名前長フィールド配置が異なる（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1509-1527,1532-1545`）。
- 各 entry の tensor 名長は 1〜1024 byte。名前は `model.dfly_layers.` で始まり、ロード済みモデルの manifest に存在し、payload byte 数が manifest と一致する必要がある（同 `:1535-1562`）。

## 実行時の動作

parser は値を `dfly_override` に保存する。`--serve` の場合は値を `ServeOpts::dfly_override` に渡し、モデルロード成功後に `load_dfly_override` を呼ぶ。通常実行でも `load_gpu_model` 成功後に同じ関数を呼ぶ。したがってモデルロードに失敗した場合は override 検証に進まない。また `--load-only` でも override 適用後に終了する（`engine/src/hy4flash/run/hy4_main.hip.cpp:407,555-571,658-665`; `engine/src/hy4flash/run/hy4_serve.hip.h:43-56,293-304`）。

loader は各 entry の payload を読み、manifest の offset を使って `g.d_trunk` の該当領域へ `hipMemcpy(..., hipMemcpyHostToDevice)` する。対象は DFly 層テンソルで、コメント上も target model weights には触れない設計とされている（実際の対象名検査・コピーは `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1509-1510,1546-1565`）。

この実装で確認できる互換性検査は tensor 名と byte 数までで、モデル識別子やファイル全体の checksum 検査は見当たらない。entry を順に適用し、重複名を拒否する検査はないため、重複があれば後の entry が同じ領域へ書き込む。規定 entry の後に余分な trailing bytes があるかを検査する処理も見当たらない（同 `:1532-1572`）。

## 適用条件と副作用

- CUDA/HIP の Hy4 実行経路が対象。`--serve` と通常実行の双方に適用される。Metal 版の実装も索引にはありますが、parser・実装が別ファイルなのでこの文書の仕様には含めない。
- ファイルをバイナリ読み込みし、各 payload を GPU 上の trunk メモリへ転送する。ファイル作成・書き換えは行わない（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1511-1514,1564`）。
- entry の途中で不正データを検出すると false を返して処理を失敗させる。その前に成功した entry の GPU 書き込みを巻き戻す処理はないため、失敗終了までの間に一部 entry が適用済みとなる場合がある（同 `:1532-1567`）。
- 有効な override は stderr に適用 tensor 数、総 byte 数、形式名、パス、所要時間を出す（同 `:1568-1571`）。

## 出力とエラー

- 通常実行では読み込み失敗時に stderr へ `dfly-override: <理由>` を出し、終了コード `1` を返す。失敗理由にはファイルを開けない、header/magic 不正、entry の切り詰め、DFly 以外の tensor 名、manifest にない名前、byte 数不一致がある（`engine/src/hy4flash/run/hy4_main.hip.cpp:660-663`; `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1513-1562`）。
- `--serve` では失敗理由を `ERR <理由>` の1行で stdout に出し、終了コード `1` を返す。プロトコル出力は改行して flush される（`engine/src/hy4flash/run/hy4_serve.hip.h:73-82,298-303`）。
- entry を一つも適用できずに loader が正常終了する経路は通常ありません。header の count が 1 未満なら header error となり、count が正なら各 entry 成功時に適用数が増えます（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:1517-1520,1564-1571`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:347,375-384,407` — 値の初期値、引数取得、値不足時の出力と終了。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:555-571,658-665` — serve への転送、通常実行でのモデルロード後の適用、および `--load-only` より前に適用する順序。
- `engine/src/hy4flash/run/hy4_serve.hip.h:43-56,293-305` — serve 設定とモデルロード後の適用。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:1509-1573` — 対象テンソル、形式、entry 検査、GPU コピー、成功ログと失敗理由。
- `docs/cli/README.md:1277-1293` — `strata-hy4` の CUDA/HIP root スコープと対象 option の索引リンク。Metal は `:1358-1374` の別スコープ。

調査時点の Strata checkout は `73d4f4196c25a65e02f6b9ef25d354826ce55105`、`git status --short --branch` は `## main...origin/main` で、未コミット変更は表示されなかった。CLI `--help` は補助資料として使用していない。

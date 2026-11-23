# `strata-hy4-metal --info`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal runner） |
| オプション | `--info` |
| 別名 | なし |
| 値 | 任意。指定する場合は直後の引数を `.strata` ファイルのパスとして扱う |

## 役割

Hy4-Flash Metal runner のビルド情報、または `.strata` モデルの基本情報を、機械処理しやすい `key=value` 形式で標準出力へ表示して終了します。引数なしならビルドの機能情報、ファイルを付けると manifest に基づくモデル情報を表示します。この分岐はモデルの Metal runner 初期化より前に実行されるため、通常の推論・GPU 初期化を行わず情報だけを確認できます（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1441-1455,1575-1582,1611-1617`）。

## 使い方

```sh
# このビルドの能力情報を表示
strata-hy4-metal --info

# モデル manifest の基本情報を表示
strata-hy4-metal --info SQ64.strata
```

## 値と既定値

- `--info` の直後に引数がなければ、ファイルは開かず `arch=hy4flash drafter=dfly2 images=<値> backend=metal` を出力して終了コード 0 で返ります。ここで `drafter=dfly2` はビルド情報の固定値で、モデルに drafter tensor が含まれるかを調べた結果ではありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1575-1580`）。
- 直後に引数があれば、その引数をファイルパスとして読みます。パス形式や拡張子に対する CLI 側の個別 validation はありません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1575-1582`）。
- 明示的な数値範囲、空文字列の拒否、複数回指定時の規則は実装されていません。最初の `--info` 分岐で直ちに return するため、後続の引数や別オプションは処理されません。

## 実行時の動作

ファイル指定時は `StrataFileReader::open` で `.strata` ファイルを開き、manifest を取得して `parse_manifest` に渡します。出力は `arch=hy4flash layers=<層数> hidden=<隠れ幅> vocab=<語彙数> experts=<expert数> eos=<EOS id> drafter=<値> images=<値> backend=metal` の1行です（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1442-1455`）。`drafter` は manifest の trunk tensor 一覧に DFly2 用の2 tensor が両方ある場合に `dfly2`、それ以外は `none` になります。`images` は `HY4_METAL_IMAGES` のビルド値です（同:1450-1454）。

`--info` がファイルを指定した場合も、引数なしの場合も、この分岐から直ちに終了するため、`--model` の読込や Metal device の初期化には進みません（同:1575-1582,1611-1622）。ただしファイル指定時の reader はファイルを読みます。

## 適用条件と副作用

- 出力値の意味はビルド条件に依存します。`images` はリンクされた Metal ViT の有無を示す値として出力され、`HY4_METAL_IMAGES` が未定義のときの定義値は `1` です（`engine/src/hy4flash/metal/hy4_metal_serve.h:20-22`）。
- 通常の `build_mac.sh run` は Section 0 の manifest を zstd 展開する reader を組み込み、sidecar を必要としません（`engine/src/hy4flash/metal/build_mac.sh:35-47`）。同スクリプト内の補助ビルド `build_vis.sh` は `strata_reader_nozstd.cpp` を使い、`<ファイル名>.manifest.json` の sidecar から manifest を読みます（`engine/src/hy4flash/metal/build_vis.sh:17-19`、`engine/src/hy4flash/metal/strata_reader_nozstd.cpp:70-77`）。そのビルドで sidecar がない場合、reader は空の manifest のまま成功し得ますが、続く manifest parse の結果はこのオプション内でエラー処理されていません（`engine/src/hy4flash/metal/strata_reader_nozstd.cpp:70-77,93`、`engine/src/hy4flash/metal/hy4_metal_main.cpp:1449-1454`）。
- ファイルの書き換え、モデルのロード、GPU 実行はこの分岐では行いません。

## 出力とエラー

- 成功時は上記の `key=value` 1行を stdout に出力し、終了コード 0 を返します（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1453-1455,1577-1581`）。
- `StrataFileReader::open` が失敗した場合は `open: <理由>` を stderr に出し、終了コード 1 で返ります（同:1443-1448）。通常 reader はファイルを開けない、4 KiB header frame の短い読込、magic 不一致、section 数の不一致、section の非整列などを失敗理由にします（`engine/src/artifact/strata_reader.cpp:33-67`）。sidecar reader では対応する header 検査を行います（`engine/src/hy4flash/metal/strata_reader_nozstd.cpp:32-68`）。
- manifest の JSON 構文不正や必須項目の欠落について、`print_info` には例外捕捉や専用エラー出力がありません。どの診断・終了状態になるかはこの経路のソースから確認できないため、ここでは断定しません（`engine/src/hy4flash/metal/hy4_metal_main.cpp:1449-1454`、`engine/src/hy4flash/run/hy4_manifest.h:78-113`）。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1575-1582` — parser 分岐。引数なし／ありの違いと即時 return。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1442-1455` — ファイルを開き、manifest を解析して情報を出力する処理。
- `engine/src/hy4flash/run/hy4_manifest.h:78-113,127-139` — manifest から設定値・tensor 一覧を読む処理。
- `engine/src/artifact/strata_reader.cpp:33-110` — 通常 reader の header 検査と Section 0 manifest 展開。
- `engine/src/hy4flash/metal/strata_reader_nozstd.cpp:32-93` — sidecar reader の header 検査と manifest 読込。
- `engine/src/hy4flash/metal/build_mac.sh:35-47`、`engine/src/hy4flash/metal/build_vis.sh:17-19` — runner と補助ビルドで使う reader の違い。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:20-22` — `HY4_METAL_IMAGES` の既定値。

# `--info`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-metal`（Metal） |
| オプション | `--info` |
| 別名 | なし |
| 値 | 必須。モデル `.strata` ファイルのパス |

## 役割

`.strata` ファイルの Section 0 にある Inkling manifest を読み、モデルの基本情報を1行で表示します。Metal device や推論 runner を初期化せずに情報を確認する経路です。実装は `.strata` コンテナを直接読み込むため、他形式の読み込みはこのオプションでは確認できません。

## 使い方

```sh
strata-inkling-metal --info ./model.strata
```

Vision ファイルの指定も出力の `images` 表示に反映できます。

```sh
strata-inkling-metal --info ./model.strata --vision ./vision.strata
```

## 値と既定値

モデルパスを1つ取ります。値の形式・拡張子を parser が検証する処理はなく、ファイルを開いて `.strata` の先頭フレームと Section 0 を読み、manifest として解析します。パスの既定値はありません。`--info` の直後に値がなければ `missing value for --info` を stderr に出し、終了コード 2 で終了します（`engine/src/inkling2/metal/ink_metal_main.cpp:432-442`）。

## 実行時の動作

parser は `--info` の直後の引数をモデルパスとして取り、その場で情報表示関数を呼び出して終了します。`--info` 後方にある引数から `--vision` とその値を走査しますが、Vision ファイル自体は開かず、パスが見つかったかどうかだけを `images=1` または `images=0` として出力します。`--vision` が `--info` より前に置かれている場合はこの走査対象になりません。`--info` の処理は引数解析を打ち切るので、それ以外の後続オプションは処理されません（`engine/src/inkling2/metal/ink_metal_main.cpp:439-446`）。

表示関数はファイルを読み取り専用で開き、先頭4096バイトを読み、オフセット `0x10` の Section 0 エントリから指定範囲を読み込みます。Zstandard frame の展開後、manifest を解析し、architecture、layer/visit/hidden/vocab/expert 数、EOS ID、drafter 有無、`images` フラグ、image padding ID、build 値を stdout に1行で出します（`engine/src/inkling2/metal/ink_metal_main.cpp:91-115`）。manifest は `config.text_config`、任意の `mtp_config`、`trunk_tensors` などから値を取り出します（`engine/src/inkling2/metal/ink_metal_common.h:221-316`）。

## 適用条件と副作用

`.strata` の Section 0 manifest を解釈できるファイルが必要です。通常のモデル実行に進む前に `return print_info(...)` するため、Metal context の作成、モデル重みのロード、warm-up、生成は行いません（通常実行の初期化は `engine/src/inkling2/metal/ink_metal_main.cpp:470-493`）。ソース上で確認できる副作用はモデルファイルの読み取りと標準出力・標準エラーへの表示です。出力ファイルの作成やモデルの変更はありません。

## 出力とエラー

- 成功時は stdout に `arch=inkling2_loop` から始まる1行を出し、終了コード 0 を返します（`engine/src/inkling2/metal/ink_metal_main.cpp:112-115`）。
- ファイルを開けない場合は `cannot open <path>` を stderr に出し、終了コード 1 です（同 `:91-94`）。
- 4096バイトの先頭読み込み、Section 0 の読み込み、Zstandard 展開に失敗した場合は終了コード 1 です。前二者と Zstandard エラーでは、この関数から追加のエラーメッセージは出ません（同 `:94-108`）。
- manifest 解析に失敗した場合は parser のエラー文字列を stderr に出し、終了コード 1 です（同 `:110-111`）。

## 根拠

- `engine/src/inkling2/metal/ink_metal_main.cpp:432-446` — Metal CLI の引数処理、必須値取得、後続 `--vision` の走査、早期 return。
- `engine/src/inkling2/metal/ink_metal_main.cpp:91-115` — ファイル読み込み、Section 0 展開・manifest 解析、成功出力と失敗経路。
- `engine/src/inkling2/metal/ink_metal_common.h:221-316` — manifest の必須・任意フィールドの解析。
- `engine/src/inkling2/metal/ink_metal_main.cpp:470-493` — 通常実行における Metal context とモデル・runner 初期化。`--info` の早期 return との違いを確認。

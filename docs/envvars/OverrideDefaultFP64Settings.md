# `OverrideDefaultFP64Settings`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Strata がこの名前の値を engine 内で読み取って設定を判定する実装はありません。確認できる Strata 側の役割は、Intel Arc Alchemist 用の SYCL serve 設定に `"OverrideDefaultFP64Settings": "1"` を書き込み、SYCL 起動 wrapper からコンテナ内へ環境変数として転送することです。ドライバー等が転送後の値をどう解釈するかは、この文書の対象外です。

## 値と判定

Strata の engine による値の parse、数値変換、真偽判定はありません。setup は対象カードなら常に文字列 `"1"` を設定します。SYCL wrapper は環境から同名の変数が列挙されるとその値を受け取りますが、Docker に渡す直前に値が完全一致の `0` または空文字なら除外します。それ以外は文字列のまま `-e NAME=value` で渡し、数値・大小文字・空白などの検査はしません。

| 経路 | 未設定 | 値 `0` | 空文字 | その他の値 |
|---|---|---|---|---|
| Alchemist 向け setup が作る config | `"1"` を設定 | 該当なし（setup は既存 `env` を引き継がず、固定値を作る） | 該当なし | `"1"` を設定 |
| `strata-sycl.sh` の Docker 転送 | 対象の環境変数がなければ転送しない | 転送しない | 転送しない | そのまま転送 |

serve 起動では `child_env()` が親プロセス環境を基にし、その後 config の `env` を同名キーへ適用するため、config が親環境値より優先します。setup が生成する Alchemist config では固定値 `1` になります。直接 wrapper を実行する場合は、wrapper の起動環境にある値が対象です。CLI 引数による優先順位や engine 側の fallback はありません。

## 有効になる条件

- `setup_intel.py` が Linux 上で検出した Intel Arc を選択し、`to_sycl()` の `alchemist` 判定が真の場合に config へ設定します。判定は driver が `i915`、または PCI device ID が `56a0`, `56a1`, `56a2`, `56a5`, `56a6`, `5690` のいずれかです。Windows では setup が Intel GPU を列挙しません。
- 他の Arc（Alchemist ID ではなく `i915` でもないカード）には setup はこの値を書きません。ただし、利用者が serve config または wrapper の環境に値を与えれば、一般的な環境転送経路の対象になります。
- SYCL serve の実行では `strata-sycl.sh` が `OverrideDefaultFP64Settings` を明示的に転送対象に含めます。Docker に値が渡るには `0` 以外かつ空文字以外である必要があります。
- この変数が転送されたことで Strata engine が起動成功するか、FP64 処理が可能になるかは Strata ソースだけからは確認できません。setup のコメントと `docs/INTEL.md` は Alchemist の FP64 設定としてこの名前を並べていますが、外部 driver 側の効果を Strata の動作としては扱いません。

## 実行時の詳細

setup は選択したカードの driver と device ID から `alchemist` を判定し、3つの設定 (`IGC_EnableDPEmulation`, `OverrideDefaultFP64Settings`, `NEOReadDebugKeys`) を config の `env` にまとめて記録します。setup の変換処理は入力 config の `env` を出力 config から除外するため、ここでは既存値の有無を読んで判断するのではなく、Alchemist 条件で固定値を生成します。

serve は engine 用環境を組み立てる際に config の `env` を親環境へ適用します。SYCL wrapper は Bash の `compgen -e` で環境変数名を列挙し、対象名を連想配列に取り込み、`0` と空文字を除いて Docker の `-e` 引数にします。値の Strata 側 cache、起動後の再読込、警告・ログ、エラー判定は実装されていません。値の解釈や、その結果として生じる失敗・挙動は外部側に属し、この調査では確認していません。

## 根拠

- `sycl/setup_intel.py:53-57` — Alchemist device ID の集合。
- `sycl/setup_intel.py:277-297,344-380` — SYCL config 変換と Alchemist 判定、対象値を含む設定の生成。`369` 行で入力 config の `env` を除外し、`385-386` 行で生成した env を出力へ格納。
- `sycl/setup_intel.py:391-397,479-491` — Windows では Intel GPU 列挙を行わず、選択 GPU 情報を `to_sycl()` に渡す setup 経路。
- `serve/server.py:4054-4068,9721-9729` — 親環境から engine 環境を作り、config `env` の値を文字列として適用する serve 経路。
- `sycl/serve/strata-sycl.sh:13-16,31-43,46-52` — 許可名としての動的取得、`0` / 空文字の除外、Docker 環境への転送。
- 名前の全参照検索では上記の setup と wrapper のほか、`sycl/probe/fp64_cost.cpp:4` のコメント、`docs/INTEL.md:244` の記述が見つかりました。probe の箇所はコメントのみで、engine による読み取り実装ではありません。

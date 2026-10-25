# `--mtp-max-t`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の Strata 作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数） |
| オプション | `--mtp-max-t` |
| 別名 | なし |
| 値 | 整数 `M`。parser は `atoi` で読み、負数を 0 に補正 |

## 役割

MTP drafter が提案する speculative verify window の最大幅をトークン数で制限します。0 は上限なしという意味ではなく、`--spec` の幅をそのまま MTP の上限として使います。`--spec` より大きい正数を指定しても、実際の MTP 上限は `--spec` までです。MTP の上限を抑えつつ、prompt lookup が条件に合えばより長い window を選べる構成に使います。

## 使い方

```sh
strata --pack ./model --tokens "1,2,3" --mtp ./draft --spec 6 --mtp-max-t 4
```

この例では `--spec 6` が全体の verify 幅を決め、MTP 自体の window は最大4トークンです。`--mtp` と `--spec` が MTP 利用条件を満たす必要があります。

## 値と既定値

- 値は必須で、既定値は `0` です。値の指定を忘れると parser の `next()` が `<option> needs a value` を stderr に出して終了コード2で終了します。
- `atoi` の結果に `max(0, ...)` を適用します。したがって負数と整数として読めない文字列は 0 相当になります。厳密な数値形式・上限の validation はこの parser にありません。値の反復指定についても個別エラーはなく、引数を順に処理するため後の指定が前の値を置き換えます。
- 初期値 0 は `Options` の定義にあります。help は `M` を「M tokens」、0 を「`--spec`」と説明します。

## 実行時の動作

parser は `o.mtp_max_t` に値を格納します。通常の generate 経路では `S_mtp = min(M, --spec)`（M が正の場合）として MTP window 上限を求め、MTP drafter に `S_mtp - 1` drafts を設定します。M が 0 の場合は `S_mtp = --spec` です。通常の逐次 decode でも window の初期幅・確率閾値による幅が `S_mtp` を越えないよう使われます。根拠は `src/program/generate.cpp:11172-11178, 14354-14362, 14880-14888` および `src/program/generate.cpp:16426-16429, 16531-16543` です。

`--suffix-draft` との相互作用:

- `--suffix-draft` は既定値が3です。`M=0` かつ `--spec >= 2` なら、初期化時に元の `--spec` を `mtp_max_t` に設定し、全体の `--spec` を最大8まで2増やします。したがって MTP の幅は元の `--spec` に留まり、suffix lookup がより広い verify window を使える余地ができます。
- `M>0` を明示するとこの自動拡張条件を満たさず、上記の自動変更は行われません。suffix lookup 自体は別途有効条件を評価し、候補幅が MTP 幅を上回ることがあります。
- `--suffix-draft 0` は suffix drafter を無効にします。この場合、このオプションが 0 でも suffix 用の幅拡張はありません。

これらは `src/program/generate.cpp:773-779, 3205-3211, 14892-14902, 16555-16562` にあります。

`--lookup-chain K` が正で、`--spec >= 2` の場合は、チェーン用に全体の `--spec` を必要に応じて拡張し、`mtp_max_t` が0なら元の `--spec` を MTP 上限に設定します。明示した M は全体幅の算出にも使われ、全体幅は最大8です。実際の追加 lookup は `use_mtp`、通常の window、suffix lookup が選ばれていないこと等の条件付きで、追加数も room と `K` の範囲に制限されます（`src/program/generate.cpp:3212-3219, 16569-16584`）。

## 適用条件と副作用

- 実際に MTP の drafts 数を変えるのは `use_mtp` が真の経路です。MTP pack が指定されていても `--spec < 2` の場合は MTP pack を無視してクリアするコードがあります（`src/program/generate.cpp:5454-5462`）。`--mtp-max-t` 単独では MTP を有効化しません。
- 値は CLI 起動時に一度読み取られ、生成中に変更する処理は確認できません。window 幅と drafter の設定に影響しますが、このオプション固有のファイル書き込みやネットワーク処理は確認できません。
- MTP 上限を超える幅は、MTP の候補ではなく suffix/chain lookup の候補として使われる場合があります。suffix lookup は一致候補と draft policy の選択条件を満たしたときだけ採用されます（`src/program/generate.cpp:14892-14920, 16569-16584`）。
- `--pipeline-windows >= 2` では drafter の load 幅自体は固定最大幅で確保されますが、後段では `S_mtp` に基づいて drafter の draft 数を制限します（`src/program/generate.cpp:5468-5472, 11172-11176`）。
- `--draft dflash2` のカード別 cap 等で後から全体 `o.spec` が下げられる経路があります。その場合も `S_mtp` はその時点の `o.spec` を上限に `min` します（`src/program/generate.cpp:5498-5503, 11172-11174`）。

## 出力とエラー

`--mtp-max-t` 専用の拒否・警告経路は parser と使用箇所から確認できません。値の欠落は終了コード2、未知の引数は `unknown argument` と usage を stderr に出して終了コード2です（`src/program/generate.cpp:2416-2423, 2787-2793`）。MTP pack の読込失敗など、後続の一般的な engine エラーはこの値固有の失敗とは区別してください。

## 根拠と調査範囲

- parser、値の補正、既定値、help 記載: `src/program/generate.cpp:778-779, 935-939, 2671-2675`。
- 自動幅調整・相互作用: `src/program/generate.cpp:3205-3219`。
- MTP の利用条件と幅適用: `src/program/generate.cpp:5454-5472, 11172-11188, 14354-14362, 14880-14920, 16426-16429, 16531-16584`。
- スコープは索引の `strata-engine` 最上位引数（`docs/cli/README.md:1128-1137`）です。`--model` / `--native` の GGUF が Qwen3.5 MoE の場合は別の `strata::qwen35::run` に振り分けられるため、この文書ではその別実装の挙動を主張しません（`src/program/generate.cpp:2393-2407`）。
- 調査ではソース checkout と既存の help 文言を読み合わせました。ビルド済み CLI の help 実行、Release artifact の確認、ビルド、GPU 実行、性能測定、テストは行っていません。

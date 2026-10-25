# `--no-fast-select`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--no-fast-select` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

QSA の候補セル選択で既定の高速なブロック top-k 経路を無効にし、従来のセル単位の選択経路を使います。A/B 比較用フラグとして `Options::no_fast_select` に保持されます（`src/program/generate.cpp:608, 2786`）。

## 使い方

```sh
strata generate --pack pack/full --tokens "1,2,3" --no-fast-select
```

`--tokens` はこの実行例のプロンプト token ID 列です。engine の `generate` 形式は `src/program/generate.cpp:806-812` にあります。

## 値と既定値

- 値は不要です。parser は引数文字列との一致時に bool を `true` に設定し、後続値を読み取りません（`src/program/generate.cpp:2416-2424, 2781-2787`）。
- 既定値は `false` です。したがって未指定なら高速選択が有効で、指定すると無効になります（`src/program/generate.cpp:608, 3926-3929`）。
- 同じフラグを複数回指定しても、同じ bool を `true` にするだけです。値の範囲検証はありません（`src/program/generate.cpp:2786`）。

## 実行時の動作

engine は初期化時に `layer_set_fast_select(!o.no_fast_select)` を呼び出します（`src/program/generate.cpp:3926-3929`）。QSA レイヤーのデコードでは、フラグ未指定時はブロック単位の FP32 スコア計算とブロック radix top-k (`qsa_block_scores` / `qsa_block_topk`) を選びます。フラグ指定時は `qsa_index_step` と `topk_512_step` を使うセル単位の経路に切り替えます（`src/core/layer.cpp:1250-1262`）。公開ヘッダーも、切り替え先を FP64 row scores と bit-serial cell top-k と説明しています（`include/strata/core/layer.hpp:495-497`）。

この選択は verify 実行にも関係します。verify window は既定 decode 経路の再現を要求し、fast select が無効なら `layer_verify_compatible` が「the block top-k selection is off」を理由に不適合を返します。verify 初期化側はこの理由を `verify: ... (the verify window reproduces the default native decode path)` としてエラーにします（`src/core/layer.cpp:537-546`; `src/core/verify.cpp:732-735`）。

## 適用条件と副作用

- オプションは通常エンジン parser に定義されています。Qwen3.6 (`qwen35moe`) のモデルでは parser より前に専用 engine へ引き渡されます（`src/program/generate.cpp:2393-2407`）。専用 parser はこのフラグを固有オプションとして受理しません。`--serve` より前に現れるなど `serve_mode` がまだ有効でない位置では usage を出して終了コード `2`、`serve_mode` 有効後では未知の `--` 引数として警告し、値らしい次引数があればそれも読み飛ばします（`src/qwen35/q36_engine.cu:3742-3795`）。
- SYCL engine にも同名 parser、設定反映、選択分岐があります（`sycl/src/program/generate.cpp:586, 2064, 3004-3007`; `sycl/src/core/layer.cpp:1295-1305`）。
- このフラグ自体はファイルや環境変数を書き換えません。ソースは性能上の優劣を保証していないため、速度差はここでは断定できません。

## 出力とエラー

通常 engine parser ではこのフラグに専用の出力や値 validation はありません。未知の引数を渡した場合は `unknown argument: ...` と usage を stderr に出して終了コード `2` になります（`src/program/generate.cpp:2786-2792`）。Qwen3.6 専用 parser での未知引数の扱いは前節のとおりです。

## 根拠

- parser、既定値、通常 engine への反映: `src/program/generate.cpp:608, 2416-2424, 2781-2792, 3926-3929`
- QSA の二つの選択経路: `src/core/layer.cpp:1250-1262`; 切替 API の説明: `include/strata/core/layer.hpp:495-500`
- verify の互換条件と失敗: `src/core/layer.cpp:537-546`; `src/core/verify.cpp:732-735`
- Qwen3.6 の委譲と parser: `src/program/generate.cpp:2393-2407`; `src/qwen35/q36_engine.cu:3742-3795`
- SYCL 対応箇所: `sycl/src/program/generate.cpp:586, 2064, 3004-3007`; `sycl/src/core/layer.cpp:1295-1305`

調査は上記 commit のソースを対象に行いました。Release 配布バイナリでの受理状況、実機 backend ごとの性能差は確認していません。

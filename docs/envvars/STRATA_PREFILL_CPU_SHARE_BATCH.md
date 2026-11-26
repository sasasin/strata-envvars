# `STRATA_PREFILL_CPU_SHARE_BATCH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--serve --batch N` の prompt 処理にも CPU expert pool を渡す opt-in です。batch slots が decode 中は prompt 側の CPU share を止め、decode 中でない prompt read では使えるようにします。batch slot の decode と prompt read が同時に同じ pool を使うことを避ける制御です。この変数は batch 時に pool を prompt path へ渡し、通常 batch では対象外の default-share 判定にも入れるため、条件を満たせば default share が有効になります。`STRATA_PREFILL_CPU_SHARE` の明示値は default 判定より優先されます（`engine/src/program/generate.cpp:11868-11883,12374-12385`、`engine/src/prefill/prefill.cpp:4630-4639`）。

## 値と判定

値全体の parse や数値変換はせず、`getenv` が非 null で先頭 byte が文字 `'1'` かを判定します。未設定、空文字、先頭が `1` 以外なら false。従って `1`、`10`、`1anything` は true、`0`、`01`、`2`、`true`、` 1`、空文字は false です。大文字小文字・後続文字・数値妥当性の検査はありません（`engine/src/program/generate.cpp:11868-11871,20757-20767`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| 全 build（対象変数の判定） | false | 先頭 byte が `1`（例: `1`, `10`, `1anything`） | 空文字、`0`, `01`, `2`, `true`, ` 1` など先頭 byte が `1` でない値 |

## 有効になる条件

- 実際の対象経路は `--serve` の batch prompt read です。`--batch` が 0 以下なら prompt path は元から pool を受け取るため、この変数による batch 向けの追加効果はありません（`engine/src/program/generate.cpp:11872,12302,12374-12380`）。
- `--batch` が正でも `--no-pool` を指定すると `serve_share_pool` は false になり、prompt path に pool は渡されません（`engine/src/program/generate.cpp:846,1384,3931,11872,13024-13032`）。
- CPU share を使うには `STRATA_PREFILL_CPU_SHARE` の判定も通る必要があります。batch 時にこの対象変数が true なら、CUDA の 1 GPU layout（または CUDA の 2-card layer split で `STRATA_SPLIT_CPU_SHARE` が unset / on）かつ GPU cache に未常駐 expert がある場合、`STRATA_PREFILL_CPU_SHARE` 未設定時でも default share が arm されます。default share は host-memory gate によって disarm されることがあります。HIP build は `arm_cpu_share` の default が gfx12 / discrete gfx11 に限定され、SYCL build はこの default-arm 分岐を持ちません。`STRATA_PREFILL_CPU_SHARE=0` は off、明示的な非ゼロ値または `auto` は layout / work の default 条件を越えて share を有効にし得ます（値の parse は同変数の実装に従います）（`engine/src/program/generate.cpp:11872-11883,12386-12392`、`engine/include/strata/prefill/share_rules.hpp:102-118`、`engine/src/prefill/prefill.cpp:691-704,3812-3868`）。
- prompt `Prefill` が pool を受け取り、対象 chunk が `stream_all` でも `pipe_chunked` でもない場合に share の候補になります（`engine/src/program/generate.cpp:13024-13032`、`engine/src/prefill/prefill.cpp:4630-4639`）。
- batch slots が 1 つ以上 active なら share gate が blocked になります。`STRATA_BATCH_CONCURRENT_READ` の concurrent-read 経路は slot decode と read を重ねるため、別途常に blocked にします（`engine/src/program/generate.cpp:20757-20767,20893-20910`）。
- 対象変数の読み取り自体に OS / backend / build macro の条件分岐はありません。CPU share の backend・GPU・モデル等の適用条件は別の機能側に属し、この調査では対象変数だけから有効範囲を追加推定しません。

## 実行時の詳細

serve 初期化で `share_batch_env` を関数内 `static const bool` として一度読み、`--batch` が正の場合に限り `serve_share_pool` を通じて pool の割当条件を変えます。batch read の `share_gate` 内にも別の `static const bool on` 読み取りがあり、初回 gate 時に cache して診断ログの出力だけに使います。通常のプロセス実行では起動後の環境変更は想定されず、pool 割当判定は再評価されません。batch read の `share_gate` は各 `run` の直前に active slot 数を数え、`Prefill::set_share_blocked(busy > 0)` を呼びます。batch のパイプライン read でも reader 起動前に同 gate を設定します（`engine/src/program/generate.cpp:11868-11883,20757-20767,20776-20786,20877-20885,21184-21195`）。

`Prefill` 側は pool があり、CPU share が on で、chunk が `stream_all` / `pipe_chunked` ではなく、share gate が blocked でないときに pool を取ろうとします。blocked の間は prompt chunk が CPU share を取らず、slot window が pool を使える状態を保ちます（`engine/src/prefill/prefill.cpp:4630-4639`）。CPU share は CPU 側の activation format を使うため GPU の結果と bit-identical ではない旨が実装コメントにあります（`engine/include/strata/prefill/prefill.hpp:301-308`）。

## ログと測定値

`STRATA_PREFILL_CPU_SHARE_BATCH` の先頭が `1` で、`--batch` が正かつ `--no-pool` でないと、serve 初期化時に次の stderr 行を出します（`engine/src/program/generate.cpp:12376-12380`）。

```text
strata serve: STRATA_PREFILL_CPU_SHARE_BATCH=1: the prompt path may use the CPU pool beside the %lld batch slots, for a read with no slot decoding
```

share gate が有効値を認識した場合は、最初の 4 回まで次の stderr 行も出します。`%s` は `off` または `on`、`%d` は active slot 数です（`engine/src/program/generate.cpp:20762-20767`）。

```text
strata batch: CPU share for this read: %s (%d slot(s) decoding)
```

この環境変数に固有の性能測定値は、参照したソース資料に条件付きで記載されていません。最初の serve ログは pool を prompt path に渡す条件を示すだけです。default share が host-memory gate によって disarm される場合や、`STRATA_PREFILL_CPU_SHARE=0` の場合もあり、この行だけで CPU share の実行は判断できません。

## 根拠

- `engine/src/program/generate.cpp:11868-11883` — 1 回目の値判定、batch の pool 条件、share arm 条件。
- `engine/src/program/generate.cpp:12374-12392` — serve の告知ログと cache / host-memory gate。
- `engine/src/program/generate.cpp:13024-13032` — CPU pool を prompt path に渡す箇所。
- `engine/src/program/generate.cpp:20757-20767,20877-20885,20893-20910,21184-21195` — 2 回目の値判定、slot 状態による gate と read 経路。
- `engine/src/prefill/prefill.cpp:691-704,3812-3815,3868,3907,4630-4639` — CPU share の判定、blocked flag、chunk 実行条件。
- `engine/include/strata/prefill/prefill.hpp:301-324` — CPU share と batch gate の API / 動作コメント。
- `engine/include/strata/prefill/share_rules.hpp:102-118` — default share が対象となる cache 条件と GPU layout。

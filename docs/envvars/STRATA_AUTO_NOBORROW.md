# `STRATA_AUTO_NOBORROW`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

単一 GPU の自動 expert cache が profile に載る全 expert を保持でき、複数 request 用 batch prefill が cache slot を借りている場合に、prompt buffer 用の cache slot loan をやめる自動判定を無効化します。loan を止めると prompt path は自前の GPU buffer を確保します。条件に合うときの既定動作は自動判定を行うことで、この変数を `0` で始まる値にすると従来の loan を維持します。

## 値と判定

変数は `std::getenv()` で読み、値全体の parse はせず先頭文字だけを調べます（`src/program/generate.cpp:7814-7816`）。

| 値 | 自動 no-borrow 判定 |
|---|---|
| 未設定 | 判定を許可（既定） |
| 空文字 | 判定を許可（設定済みだが先頭文字は `\0` であり `'0'` ではない） |
| 先頭文字が `0` | 判定を行わず、loan を維持。例: `0`, `0abc` |
| その他すべて | 判定を許可。例: `1`, `true`, `false`, `2abc`, 空白から始まる値 |

数値変換、文字列全体の比較、大文字小文字変換、無効値エラー、範囲制限はありません。したがって `false` も自動判定を止めません。

## 有効になる条件

対象名の読み取り自体が、次の条件をすべて満たすブロックに限られます（`src/program/generate.cpp:7804-7816`）。

- HIP、Metal、Windows ではないビルド（前置のコンパイル条件）。
- 自動 expert cache（`--expert-cache` を明示せず `auto_cache` が true）。
- profile があり、borrow が有効で、`--prefill auto` が選ばれている。
- `--batch` / `--slots` が 2 以上、単一 GPU、stage split なし。
- sized cache が profile 内の全 expert を保持し、helper GPU cache がない。

いずれかの条件が外れると、この箇所では変数を読まず、no-borrow の自動切替も起きません。特に明示的な `--prefill N` は対象外です（引数解析: `src/program/generate.cpp:3451-3459`）。`--no-prefill-borrow` が既に指定されている場合も `pf_borrow` が false となるため対象外です（`src/program/generate.cpp:3480`, `5641-5644`）。

読み取り後も、自動切替は GPU の余裕がある場合だけ実行されます。profile 全体の cache slot bytes を合算し、最大 `8192` token（`--prefill auto` の上限に応じて最低 `256` token）で必要な自前 buffer サイズを見積もります。free VRAM から cache 使用量、`--vram-reserve-mib`、pipeline の先行領域を差し引いた値が、自前 buffer 見積もりに加えて `3072 MiB` 以上あることが条件です（`src/program/generate.cpp:7817-7824`）。足りなければ loan を続けます。

`STRATA_PREFILL_BORROW` はこの判定をさらに抑止します。値の先頭文字が `1` なら loan を維持し、他の値（未設定・空文字を含む）ならこの判定を許可します（`src/program/generate.cpp:7815-7816`）。この変数が `STRATA_AUTO_NOBORROW=0` と同時に設定されても、どちらも自動切替を抑止するだけです。

## 実行時の詳細

値は cache sizing の後、prompt buffer の実行時利用より前の engine setup で直接読み取られます。static cache はありません。条件を満たしてこの地点に来たときに一度判定され、初期化済み engine の状態はその後の環境変更で再計算されません（`src/program/generate.cpp:7803-7816`）。

自動切替が許可され、VRAM の見積もりも通ると、stderr に `strata generate: every expert fits the cache; the prompt path's own buffers (...) fit (...): no loan of cache slots` が出ます。見積もりが足りない場合は同じ行の `do not fit` / `: the loan stays` が出ます（`src/program/generate.cpp:7825-7828`）。成功時には `no_prefill_borrow` を true、`pf_borrow` を false にし、自動 chunk 選択を解除して計算済み chunk を設定します（`src/program/generate.cpp:7829-7834`）。prompt path の own buffer 用サイズも `Prefill::bytes_needed_owned` で見積もっています（同: `7820-7824`）。以降の処理では `no_prefill_borrow` に応じて cache の lend 領域を作らない経路があります（同: `9812-9818`）。

この判定ブロックはエラー終了を発生させず、判定を抑止したり VRAM 条件を満たさない場合は loan 継続に戻ります。自前 buffer の後続確保が失敗した場合のエラー挙動は、この環境変数の判定箇所からは確認できません。

## 根拠

- `src/program/generate.cpp:7804-7816` — コンパイル対象、適用前提、対象変数と `STRATA_PREFILL_BORROW` の判定。
- `src/program/generate.cpp:7817-7834` — chunk / buffer / VRAM の条件、stderr ログ、成功時に no-borrow に切り替える処理。
- `src/program/generate.cpp:3451-3459,3480,5641-5644` — `--prefill` の auto 判定、`--no-prefill-borrow`、borrow 初期状態。
- `src/program/generate.cpp:9812-9818` — no-borrow 時に cache loan 計画を行わない後続経路。

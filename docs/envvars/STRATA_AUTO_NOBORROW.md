# `STRATA_AUTO_NOBORROW`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

この変数は、条件を満たしたときに Strata が自動で選ぶ「prefill が expert cache の slot を借りず、自分の buffer を確保する」経路を抑止する。既定では抑止せず、VRAM に余裕があれば借用をやめる。`STRATA_AUTO_NOBORROW` 自体は借用を直接 ON/OFF する設定ではなく、値が `0` で始まるとこの自動判定をスキップする。実装は `engine/src/program/generate.cpp` の cache sizing 後の `AUTO NO-BORROW` 分岐にある（`engine/src/program/generate.cpp:9498-9531`）。

自動判定が成立すると、expert cache の slot 数はそのままに `no_prefill_borrow` を有効にし、`pf_borrow` と `prefill_auto` を無効にして、prefill chunk を固定する。prefill 時に cache slot を借りないため、prompt 用 buffer は別に確保される（`engine/src/program/generate.cpp:9511-9528,23989-23993,24115-24120`）。この分岐は生成設定を変えるもので、生成 token の同一性をこの調査で実行検証したものではない。

## 値と判定

Strata は `std::getenv("STRATA_AUTO_NOBORROW")` の戻り値が非 null かつ先頭文字が `'0'` かだけを見る。数値変換、文字列全体の比較、大文字小文字変換はない。空文字は設定済みでも先頭文字が `'0'` ではないため抑止しない。`0`、`00`、`0anything` のように `0` で始まる文字列だけが抑止する。`false`、`true`、`1`、` 0`、未設定は抑止しない。無効値としてのエラーや警告、fallback はなく、先頭が `0` かどうかだけで分岐する（`engine/src/program/generate.cpp:9508-9510`）。

| 条件 | unset / 空文字 | 自動判定を止める値 | 自動判定を止めない値 |
| --- | --- | --- | --- |
| `STRATA_AUTO_NOBORROW` | 判定を止めない | `0`, `00`, `0anything` | `1`, `true`, `false`, ` 0`, その他 `0` 以外で始まる文字列 |

関連する `STRATA_PREFILL_BORROW` も同じ分岐で読み、先頭文字が `'1'` なら自動 no-borrow を止める。こちらも全体 parse はせず、空文字・未設定・`01` は veto にならず、`1` や `1anything` は veto になる。どちらかの veto が成立すると、この no-borrow 判定とその判定ログを実行しない（`engine/src/program/generate.cpp:9508-9510`）。

## 有効になる条件

値が `0` で始まらず、かつ `STRATA_PREFILL_BORROW` が `1` で始まらないことに加え、次の条件をすべて満たす必要がある（`engine/src/program/generate.cpp:9498-9510`）。

- コンパイル時に `STRATA_USE_HIP`、`STRATA_GPU_METAL`、`_WIN32` のいずれも定義されていないこと。同じコードの cache sizing は CUDA device の VRAM 読み取りを使う。この分岐は HIP、Metal、Windows ビルドには含まれない。
- `--expert-cache auto` 相当の自動 cache sizing (`auto_cache`) であること。`--expert-cache` は `auto` を `-1` にする。expert profile が読み込まれている場合、既定値または `--expert-cache 0` も `-1` に変換されるため自動 sizing になる。正の明示値ではこの条件を満たさない（`engine/src/program/generate.cpp:3984-3987,6746-6756,9050`）。
- profile が空でなく、cache sizing の結果 `sized_slots.size() == profile.size()`、すなわち profile の全 entry が cache に収まっていること（`engine/src/program/generate.cpp:9471-9489,9506-9507`）。
- prefill が借用可能 (`pf_borrow`) で、`o.prefill_auto` が有効であること。`--prefill auto` または `--prefill auto:N` は auto を有効にし、`--prefill N` は有効にしない。`--no-prefill-borrow` が指定されると借用できず、この分岐には入らない（`engine/src/program/generate.cpp:4000-4008,4035,6821,9506`）。
- `STRATA_PREFILL_AUTO_MAX` は `o.prefill_auto_max` の決定に使われるが、この分岐の chunk 式は 8192-token 上限を適用する。従ってこの判定で選ぶ chunk は `o.prefill_auto_max` が 8192 を超えても大きくならない（`engine/src/program/generate.cpp:4003-4008,9514`）。
- `o.batch >= 2` であること。`--slots` は `--batch` と同じ値を設定する。batch slot は `--serve` がないと無効化されるため、実際の batch 経路は server mode に限られる（`engine/src/program/generate.cpp:4041-4042,7955-7961`）。
- layer split (`multi_gpu` または `stages`) がなく、`o.expert_cache_remote` に正の helper cache がないこと（`engine/src/program/generate.cpp:9506-9507`）。
- 全 profile entry の cache 分を除いた空き VRAMに、prefill の owned buffer と 64 MiB の加算分、さらに 3072 MiB の空きを確保できること。足りない場合は借用を維持する（計算は下記、`engine/src/program/generate.cpp:9511-9528`）。

最後の fit 判定では `chunk = min(8192, max(256, o.prefill_auto_max))`、`own_mib = (bytes_needed_owned(..., chunk, ...) >> 20) + 64`、`room_mib = (free VRAM - cache bytes) / MiB - vram reserve - pipeline allocation` とし、`room_mib >= own_mib + 3072` のときだけ no-borrow に切り替える。`--vram-reserve-mib` と `--pipeline-windows` はこの fit 判定に反映される（`engine/src/program/generate.cpp:9511-9528,9052-9058`）。

## 実行時の詳細

読み取りは profile のロードと cache sizing の後、prefill の request 処理より前に行う。関数内 static cache ではなく、この初期化経路で条件が成立したときに `getenv` を呼ぶ。`--serve` の常駐 engine ではこの設定は engine 起動時の判定であり、各 request では読み直さない（`engine/src/program/generate.cpp:6746-6751,9048-9051,9506-9510,23989-23993`）。

fit した場合は `no_prefill_borrow=true`、`pf_borrow=false`、`prefill_auto=false` とし、選定した chunk を `o.prefill_chunk` に固定する。後続の prefill setup は borrow pointer を取らず、`Prefill::init` に null の borrow を渡して自前 buffer を初期化する。初期化に失敗した場合は engine が `strata generate: %s` を stderr に出して `1` を返す（`engine/src/program/generate.cpp:9523-9528,23989-23993,24115-24122`）。

server の Python wrapper はこの変数を個別に解釈しない。`child_env` は親の `os.environ` を複製し、設定の `env` をその後に適用してから engine に渡すため、設定側に同じ名前があれば親環境の値を上書きする。engine はその環境で `--serve` 起動する（`terminal/serve/server.py:833-835,4007-4028`）。

## ログと測定値

この分岐に入ると stderr に次の形式で fit 結果を出す。buffer が入る場合は `fit` と `: no loan of cache slots`、入らない場合は `do not fit` と `: the loan stays` が入る。`STRATA_AUTO_NOBORROW=0`、`STRATA_PREFILL_BORROW=1`、または先行条件不成立で分岐に入らない場合、この判定ログは出ない（`engine/src/program/generate.cpp:9518-9522`）。

```text
strata generate: every expert fits the cache; the prompt path's own buffers (%lld MiB for a %lld-token chunk) %s (%lld MiB left beside the %d MiB reserve, %lld MiB kept free)%s\n
```

この format string の `%s` は `fit` / `do not fit`、末尾の `%s` は `: no loan of cache slots` / `: the loan stays`。環境変数で抑止された場合や分岐条件が揃わない場合、このログは出ない。

fit して切り替わった後、prefill setup は `strata generate: prompt path allocates its own buffers (no cache slots to borrow)` を stderr に出す。`docs/DETAILS.md` にこの変数の測定値は見当たらず、本調査では速度や出力同一性の実測値を記載しない（`engine/src/program/generate.cpp:24115-24120`）。

## 根拠

- `engine/src/program/generate.cpp:9498-9531` — compile guard、前提条件、両環境変数の先頭文字判定、VRAM fit 判定、自動切り替え。
- `engine/src/program/generate.cpp:3984-4008,4035,4041-4042,6746-6756,6821,7955-7961,9048-9058` — cache / prefill / batch 引数、profile の既定 cache、借用状態、serve-only batch 条件。
- `engine/src/program/generate.cpp:23989-23993,24115-24122` — request 時の borrow 有無、自前 buffer 初期化と失敗経路。
- `terminal/serve/server.py:833-835,4007-4028` — server から engine への起動と環境変数の引き継ぎ。

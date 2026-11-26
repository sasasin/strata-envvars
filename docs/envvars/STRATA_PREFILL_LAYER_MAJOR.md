# `STRATA_PREFILL_LAYER_MAJOR`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA の prompt prefill を chunk-major から layer-major の super-chunk 処理に切り替える要求スイッチ。layer-major は super-chunk 内の各 sub-chunk について各 layer の attention 側を進めてから、その layer の routed experts をまとめて実行する。従来の chunk-major と expert の加算順序・MMQ の行グループが異なるため、出力は bitwise 同一とは限らない。処理可能な条件を満たさない prompt では、値が ON でも従来経路へ戻る（`engine/src/prefill/prefill.cpp:8064-8080,9657-9705`）。

通常の未設定時は OFF。例外として、生成器が単一 CUDA GPU の小さい expert cache 向け自動調整を選んだとき、条件を満たし、利用者がこの変数を空でない値にしていなければ、Strata 自身が実行環境へ `1` を設定する（`engine/src/program/generate.cpp:12561-12612`）。

## 値と判定

prefill 実行時に `lm_env_text()` が `std::getenv` で値を取得し、そのポインタを関数内 `static` に保存する。空文字列は `lm_env_explicit()` で未指定として扱われる。空でない値は `prefill_layer_major_resolve()` に渡され、`std::atoi(env) != 0` なら ON、それ以外は OFF（`engine/src/prefill/prefill.cpp:8082-8086,9657-9662`; `engine/include/strata/core/sm120_series.hpp:186-192`）。

`atoi` のため文字列全体の妥当性検査はなく、先頭の空白や符号を含む数値として読み取れる部分が変換される。たとえば `1`, `2`, `-1`, `+1`, `1abc` は ON、`0`, `0anything`, `off`, 数値として読めない文字列は OFF。空文字は resolver の既定値に進む。範囲 clamp や警告はない（同上）。

| 状況 | unset / 空文字 | 設定時に ON | 設定時に OFF |
|---|---|---|---|
| 通常の resolver（CUDA / HIP） | OFF | `atoi` の結果が 0 以外 | `atoi` の結果が 0 |
| 単一 CUDA GPU の small-card 自動設定 | 条件を満たせば Strata が `1` を設定 | 空でない値があれば自動設定しない。実行時は上記 resolver で判定 | 空でない値があれば自動設定しない。実行時は上記 resolver で判定 |

`STRATA_DEFAULTS=026` を含め、現在の `prefill_layer_major_default()` は常に false を返す。したがって未設定・空文字の既定は全 backend / stage 数で OFF。明示値は `STRATA_DEFAULTS=026` より優先する（`engine/include/strata/core/sm120_series.hpp:176-192`）。

## 有効になる条件

- 変数を非ゼロ値にしても要求を受理するだけで、Metal 実装では `Prefill::run()` が Metal 経路へ先に分岐するため、この変数を参照しない（`engine/src/prefill/prefill.cpp:9629-9651`）。
- HIP build では `STRATA_LM_HIP` の先頭文字が `1` でなければ layer-major 準備処理が「layer-major prefill has only been run on NVIDIA CUDA」として辞退する。HIP でのオプトイン後も、以下の共通条件を満たす必要がある（`engine/src/prefill/prefill.cpp:8170-8179`）。
- `hand_in_` がなく、実体 `impl_` があり、prompt に image embedding がなく、layer split の peer GPU / helper 経路でなく、split 時に PLE layer が先頭 stage に含まれること（`engine/src/prefill/prefill.cpp:9657-9662,8180-8194`）。
- `STRATA_KVA` が有効でなく、chunk 境界で yield する batch read でなく、`--prefill-pipe` による固定 chunk 計画でなく、4-bit expert slot の対象でもないこと（`engine/src/prefill/prefill.cpp:8195-8204`）。
- `STRATA_DBG_FEAT`、`STRATA_DBG_ROUTE_OVERRIDE`、`STRATA_PREFILL_DUMP_R_ALL` による routing / row debug dump がなく、expert plan と MMQ / FP16 / MoE buffers が揃っていること。WMMA 専用 layer、未対応の APR / NVFP4 形式、fused expert layout なども辞退条件になる（`engine/src/prefill/prefill.cpp:8205-8234`）。
- 通常の単一 prompt では少なくとも 2 chunks 分の prompt が必要。`STRATA_PREFILL_LM_TOKENS` を正数に設定すると chunk 1 個分まで下がる。さらに super-chunk の VRAM / pinned RAM 確保と layer split 各 stage の共通サイズ確保に成功すること。容量不足や stage 間不一致なら chunk-major に戻る（`engine/src/prefill/prefill.cpp:8235-8243,8254-8285,8343-8393`）。
- 複数 prompt の `run_multi()` はこの環境変数とは別に layer-major を強制して準備する経路があるため、この変数の値が複数 prompt 経路の唯一の有効化条件ではない（`engine/src/prefill/prefill.cpp:8409-8432`）。
- 小さい expert cache 向けの自動設定は、`chunk > 0`、自動 `--prefill`、単一 GPU、空の `stages`、`STRATA_PF_SMALL` が未設定または空でなくても先頭文字が `0` でないこと、native pack、`STRATA_DEFAULTS=026` でないこと、既存の `STRATA_PF_FUSED` が利用者指定でないこと、対象 chunk が `1..8191` であることが条件。既存の `STRATA_PREFILL_LAYER_MAJOR` が空でない場合は値にかかわらず自動設定を抑止する。`--prefill` を明示した場合は自動 chunk sizing ではないためこの自動設定経路に入らない（`engine/include/strata/core/sm120_series.hpp:195-219`; `engine/src/program/generate.cpp:12538-12578`）。

## 実行時の詳細

通常の `Prefill::run()` は prompt ごとに `lm_env_text()` のキャッシュ済みテキストを resolver で評価し、ON の場合に `lm_prepare_chain()` で容量・対応条件を調べる。準備が通れば `run_layer_major()` と `lm_run()` を実行してから pipeline を drain し、失敗時はエラーを返す。準備が通らない場合は理由を出して通常の `run_impl()` に進む。環境変数自体の読み取りは初回 `lm_env_text()` 呼び出し時の static cache なので、その後の外部からの環境変更は通常反映されない（`engine/src/prefill/prefill.cpp:8082-8086,9657-9705`）。

small-card 経路はモデルの prompt chunk を決めるときに環境を直接読み、条件を通った場合、Windows では `_putenv_s`、その他では `setenv(..., 0)` で `STRATA_PREFILL_LAYER_MAJOR=1` を設定する。新しいレイアウトの chunk sizing が失敗すれば環境変数を空 / unset に戻して既定 chunk を再計算する。この処理はプロセス内の環境を変更し、子プロセスへの転送処理ではない（`engine/src/program/generate.cpp:12561-12604`）。

## ログと測定値

- 未設定時の既定が変わり layer-major が `by_default` として選ばれた場合、プロセス内一度だけ `strata prefill: layer-major prefill is on for this layer split (each layer's experts are read once per super-chunk of up to ... tokens, not once per chunk; STRATA_PREFILL_LAYER_MAJOR=0 or STRATA_DEFAULTS=026 turns it off)` を stderr に出す（`engine/src/prefill/prefill.cpp:9661-9671`）。現行既定は OFF で、small-card 経路が設定する値は明示値扱いになるため、この枝には通常入りません。
- 準備失敗時は、短い prompt を除き、理由が直前と異なる場合 `strata prefill: layer-major off for this prompt: <理由>` を stderr に出す。同じ理由の抑制があり、長い prompt で失敗が続く場合は 16 回ごとに `strata prefill: layer-major still off, ...` も出す。短い prompt は自動既定時には理由ログを抑制する（`engine/src/prefill/prefill.cpp:9693-9703`）。
- small-card の自動設定を採用した場合は `strata serve: small expert cache: ...`、新レイアウトの chunk 確保にも失敗した場合は `strata serve: small expert cache: the unfused prompt path does not fit here; the default path stays ...` を stderr に出す（`engine/src/program/generate.cpp:12595-12612`）。
- Strata の `docs/SETTINGS.md:262` は対象 backend を NVIDIA / AMD と記載し、`docs/release-notes-0.2.7.md:20,33` は layer-major が二枚の CUDA GPU で既定 ON と記述する。一方、調査対象 commit では unset の既定は OFF で、HIP は `STRATA_LM_HIP=1` がなければ辞退し、Metal 経路はこの変数を参照しない。現行ソースを優先し、同 release note の速度測定値は現行既定の根拠として扱わない。現行コードコメント中の別環境での測定値も、本書では独自に検証していないため挙げない（`engine/include/strata/core/sm120_series.hpp:176-184`; `engine/src/prefill/prefill.cpp:8170-8179,9629-9651`）。

## 根拠

- 値の取得・変換・既定値: `engine/src/prefill/prefill.cpp:8082-8086`; `engine/include/strata/core/sm120_series.hpp:176-192`。
- small-card 条件とプロセス環境の変更: `engine/include/strata/core/sm120_series.hpp:195-219`; `engine/src/program/generate.cpp:12561-12612`。
- 実行・辞退・容量条件: `engine/src/prefill/prefill.cpp:8170-8239,8254-8285,8343-8407,9629-9705`。
- Strata 資料との照合: `docs/SETTINGS.md:262`; `docs/release-notes-0.2.7.md:20,33,66`。

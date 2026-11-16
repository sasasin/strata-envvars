# `STRATA_PREFILL_TAIL_LOAN`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

serve の prompt path で GPU cache の expert slot を一時的に借りて fused prefill buffer を置くとき、短い最後の chunk 用の buffer を要求ごとの必要量で確保する機能を制御する。既定では有効で、適用条件を満たす場合は stream floor（全 expert を stream する境界）より短い要求末尾のサイズに合わせる。`STRATA_PREFILL_TAIL_LOAN=0` は従来どおり floor - 1 token 分の tail を保持する。この設定が直接変えるのは prefill の buffer 配置と slot loan であり、同箇所に生成 token の選択やモデル重みを書き換える処理はない。読み取りは `src/program/generate.cpp` の prompt loan 計画にある。(`src/program/generate.cpp:10442-10445`, `18368-18424`, `18450-18455`)

## 値と判定

関数ローカル `static const bool` の初期化時に `std::getenv` で一度読み、値が存在し、かつ先頭文字が `'0'` の場合だけ無効にする。文字列全体の parse、数値変換、空白除去、大文字小文字変換はない。したがって `0`, `0anything` は無効、`1`, `true`, `false`, `off`, ` 0` は有効であり、空文字も「設定済み」だが先頭文字が `'0'` でないため有効。未設定も有効。(`src/program/generate.cpp:10445`)

| 条件（build など） | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 共通の値判定 | 有効 | 空文字、`1`、`true`、`false`、`off`、` 0` | `0`、`0anything` |

## 有効になる条件

- 要求の loan を作り直す prompt path であること。tail sizing は `tail_loan_on` が真で、fused buffer の tail が意味を持つ場合だけ行われる。`tail_matters` は対象 chunk が正で fused layout のとき真になる。(`src/program/generate.cpp:18423-18424`, `18450-18455`; `src/prefill/prefill.cpp:2859`)
- tail loan の再利用・要求別再配置は、単一の `PfPart`、layer split なし、複数 GPU なし、peer card なし、`--prefill-head-alias` なし、`--batch` が 1 以下の場合に限られる。条件外では要求別 tail の sizing は使われず、既存 loan の chunk 条件など従来の処理に進む。(`src/program/generate.cpp:18423-18431`)
- `STRATA_PREFILL_TAIL_LOAN=0`（先頭文字）ではこの sizing が無効となり、要求ごとの tail 計算は `-1`（stream floor - 1 分を残す既定の layout）を返す。(`src/program/generate.cpp:10445`, `18450-18455`)
- serve の auto-chunk scan で tail 0 を前提にして chunk を選び直す最適化には、さらに `STRATA_PREFILL_FUSED` が定義され `STRATA_PREFILL_MMQ` が未定義の build、`--prefill auto`、ring bytes が有効、単一 GPU（split/peer/head alias なし、batch 1 以下）、等値 chunk が選ばれていること、small-card path でないこと、chunk で fused tail が必要なことが要る。これらが揃わない場合 scan は floor - 1 の tail を数える。これは serve scan の追加条件であり、個別 request loan の上記条件とは別である。(`src/program/generate.cpp:11095-11106`, `11119-11122`, `11793-11805`; `include/strata/prefill/fit_out_rule.hpp:22-35`)

## 実行時の詳細

`tail_loan_on` は `generate.cpp` 内の関数ローカル static で、最初にその宣言を実行する時に環境を読み、以後そのプロセスで値を再取得しない。起動後に環境値を変更しても反映されない。未設定時の既定は有効。CLI にはこの値判定を上書きする設定はなく、`--batch`、GPU 構成、head alias などは有効化条件として別途確認される。(`src/program/generate.cpp:10445`, `18423-18424`)

有効時、要求の token 数 `tokens` と chunk `w` から `segment_tail(tokens, w, floor_t)` で必要な tail を計算し、必要なら `relayout` で loaned buffer を再配置する。同じ chunk の tail-sized layout を再利用するときは、既存 tail が要求量をカバーする限り保持し、不足する場合は floor - 1 に戻す。loan が収まらないときは chunk を 256-token 単位で半分にして再試行し、256 以下まで縮めても必要 slot が収まらない場合は `prefill: no chunk of this request fits the slots that can be lent (#2090)` をエラーとして返す。(`include/strata/prefill/loan_rules.hpp:51-65`, `src/program/generate.cpp:18450-18455`, `18475-18482`)

tail 付きの layout を複数要求で使う際は、chunk に加えて短い末尾に必要な tail room も再利用判定に含める。tail room より長い fused chunk が stream floor より短い場合、`Prefill::run_impl` は `prefill: a chunk of ... tokens below the stream floor does not fit the fused layout's tail of ... tokens` をエラーにして処理を失敗させる。(`src/program/generate.cpp:18428-18435`, `src/prefill/prefill.cpp:4165-4172`)

## ログと測定値

tail-sized layout への `relayout` が実際に起き、tail が非負なら stderr に一度だけ `strata serve: the lent prompt buffers are sized for the request's own short last chunk (tail %lld tokens, not the stream floor's %lld); STRATA_PREFILL_TAIL_LOAN=0 keeps the floor's` と出る。要求数値は `%lld` に渡された実際の tail と `floor_t - 1`。relayout が起きない場合や tail が `-1` の場合、この行は出ない。(`src/program/generate.cpp:18494-18509`)

`docs/SETTINGS.md:349` はこの名前を NVIDIA / AMD 向けの on/off 設定として一覧掲載する。`docs/DETAILS.md` にこの変数の詳細な挙動や条件、測定値の記載は見つからなかったため、性能差は記載しない。source comment にある RTX A6000 等での別設定・tail scan の測定値は、この変数自体の比較結果として扱わない。(`src/program/generate.cpp:10442-10445`; `include/strata/prefill/fit_out_rule.hpp:6-15`)

## 根拠

- `src/program/generate.cpp:10442-10445` — 設定の既定と値判定。
- `src/program/generate.cpp:11095-11106`, `11119-11122`, `11793-11805` — serve scan の条件と tail 0 scan。
- `src/program/generate.cpp:18368-18435`, `18450-18509` — request loan の条件、tail 計算、再配置とログ。
- `include/strata/prefill/fit_out_rule.hpp:22-35` — scan 条件の判定規則。
- `include/strata/prefill/loan_rules.hpp:51-73` — tail 計算と loan 再利用条件。
- `src/prefill/prefill.cpp:2853-2859`, `4165-4172` — tail room と実行時の範囲エラー。
- `docs/SETTINGS.md:349` — docs 上の backend 一覧。

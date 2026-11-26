# `STRATA_PREFILL_PIPE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

複数段の layer split で prompt を読む際、各 stage の処理が重なるように prompt の chunk 長を計画する opt-in 値。`0` は通常の buffer chunk、`1` は既存の chunk 数を条件付きで均等化、それより大きい値はこの PC の `b/a` 比を token 単位で指定する。環境変数は `Prefill::pipe_value()` が参照し、計画は `Prefill::plan_chunk()` から `pipeline_chunk()` に進む（`engine/src/prefill/prefill.cpp:3618-3625,3647-3687`）。

この計画が働くのは prompt が 2 段以上の layer split で読まれる場合だけ。stage 数が 1、または後段 stage に hand-in 済みの場合は `plan_chunk()` が無効値を返し、通常の buffer chunk を使う（`engine/src/prefill/prefill.cpp:3678-3687,4283-4297`）。設定値そのものは生成 token 選択の設定ではなく、prompt の分割長を決める。

## 値と判定

環境変数は `std::getenv` で取得し、未設定または空文字なら `0.0`。それ以外は `std::atof` の結果を `std::max(0.0, ...)` で負値から下限 0 にする。文字列全体の妥当性検査やエラー通知はない。`atof` が認識する数値の先頭部分が使われるため、たとえば `12junk` は 12、`junk` は 0 になる。`true` / `false` は真偽値として扱われず、どちらも 0 になる。`nan` も `std::max` のこの引数順では 0、正の無限大は正値として残る（後段の ratio 計算では `2^20` token に上限をかける）。環境値は `pipe_value()` 初回評価時に static cache され、その後の環境変更は反映されない（`engine/src/prefill/prefill.cpp:3621-3625,3641-3644`）。

| 条件 | unset / 空文字 | 有効になる値 | 無効になる値・扱い |
|---|---|---|---|
| `STRATA_PREFILL_PIPE` | 0（pipe 無効） | `1` は均等化規則、`1` より大きい有限値は `b/a` 比。例: `2`, `1024`, `12junk` | `0`, 負数、`true`, `junk`, 空文字は 0 と同じく pipe 無効。正値 `0 < R < 1` は pipe を有効にし、均等化規則（比 0 として計画）を選ぶ。 |
| CLI `--prefill-pipe R` が指定された場合 | 環境変数より CLI が優先 | `atof` 後に 0 以上へ clamp。CLI も `0 < R <= 1` で均等化、`R > 1` で比を指定 | 負数・空・数値で始まらない文字列は 0。CLI 値は `Prefill::set_pipe()` に入り、環境値の評価より優先（`engine/src/program/generate.cpp:4033,6830`; `engine/src/prefill/prefill.cpp:3618-3625,3637-3639`）。 |
| serve リクエストの `pipe=R` | そのリクエストでは unset を表す `-1`。run の CLI / 環境設定を使用 | `strtof` 後に 0 以上へ clamp。非負値は run 設定を上書き | 負数は 0 へ clamp され、そのリクエストでは pipe 無効。空や非数値文字列も変換値 0。 |

`pipeline_chunk()` は段数 2 未満、prompt 長 0 以下、または cap 0 以下なら cap を返す。`R <= 1` の均等化は、現在の chunk 数が 1 より大きく、現在の末尾 chunk が `stream_all_min()` 以上の場合だけ 256 token grid に切り上げて均等化する。それ以外は cap（現在の分割）を維持する。`R > 1` は候補 chunk を探索し、現行分割より 3%を超えて良い計画がある場合だけ変更する。比は整数 token に丸めて最大 `2^20` に制限され、候補は最大 64 chunk、最小 chunk は `STRATA_PREFILL_PIPE_FLOOR` に従う（既定 512、256 token grid 上で 256..4096 に clamp）（`engine/src/prefill/prefill.cpp:3627-3634,3641-3676`）。

## 有効になる条件

- 少なくとも 2 段の layer split が構成され、先頭 stage が prompt segment を計画すること。1 GPU / 1 stage では値が正でも無効（`engine/src/prefill/prefill.cpp:3678-3687`）。
- `--prefill-pipe` を指定した場合は環境変数より優先される。serve ではリクエスト `pipe=R` が run 値より優先される。リクエストごとに request override を設定し直すため、前の request の値は持ち越さない（`engine/src/program/generate.cpp:6830,18864-18865,18925,18943`; `engine/src/prefill/prefill.cpp:3618-3625`）。
- prompt segment の予定 chunk が buffer chunk と同じなら専用計画による変更はなく、ログも出ない。既存の segment を再開する際は保存された計画が現在の `pipe_setting()` と同等な `pipe_key()` の場合に再利用される（`engine/src/program/generate.cpp:20775-20800`）。
- 設定表では NVIDIA / AMD 向けとされている（`docs/SETTINGS.md:264`）。この環境変数を読むコードは共通の prefill 実装に一箇所あり、個別 OS / build macro による別の値解釈は見当たらない。GPU 実行は行っていないため、個々の機器で split が成立する条件や性能はこの調査では実測していない。

## 実行時の詳細

CLI 引数は `std::atof` で読み、指定があれば起動設定に保存する。serve の各 request は `pipe=` key を `strtof` で読み、`Prefill::set_pipe_request()` に設定する。優先順位は request override（0 以上）、CLI（0 以上）、環境変数 static 値の順。request key がなければ `-1` の sentinel をセットして run 設定へ戻す（`engine/src/program/generate.cpp:4033,6830,18864-18865,18925,18943`; `engine/src/prefill/prefill.cpp:3618-3639`）。環境値の初回評価より前に CLI が設定されていると `pipe_value()` は CLI を返して環境値を読まない。環境値が初回に読まれた後は process 内でキャッシュされる。

先頭 stage は segment 全体の長さと stage 数を使って chunk を一度計画し、計画が有効なら各 run に `force_chunk()` で渡す。これにより分割実行、decode slot と並行する実行、checkpoint / BYIELD からの継続でも同じ segment の chunk が使われる（`engine/src/program/generate.cpp:20769-20809,20876-20885`; `engine/src/prefill/prefill.cpp:4286-4302`）。

`pipeline_chunk()` が cap より小さい chunk を選んで実際に複数 chunk へ分けるとき、stderr に次の形式で計画を記録する。設定が有効でも chunk が変わらない場合、この計画ログは出ない（`engine/src/prefill/prefill.cpp:3694-3700,4295-4302`）。

```text
strata prefill: <tokens> tokens in <chunk>-token chunks over <stages> stages (--prefill-pipe <setting>)
```

## ログと測定値

上記の stderr 計画ログが実際に chunk 数・長さを変更する場合に出る。無効値、条件不成立、または選択 chunk が現行 cap と同じ場合に、この変数専用の警告やエラーはない。通常の prompt read が失敗した場合は呼び出し側の一般的な read error 経路へ進むが、環境変数の値を理由とする失敗経路は実装上見当たらない。

`docs/MULTI_GPU.md:151` は `--prefill-pipe` / 環境変数の要約と calibration に触れている。数値測定は同資料の表にある CLI 指定の測定であり、環境変数単独の性能測定としては記載しない。

## 根拠

- `engine/src/prefill/prefill.cpp:3615-3639` — 環境値の読み取り、変換、cache、CLI / request 値の優先順位。
- `engine/src/prefill/prefill.cpp:3641-3676` — 比の丸め・上限、chunk 選択、均等化規則と改善判定。
- `engine/src/prefill/prefill.cpp:3678-3700,4283-4302` — stage 条件、実 chunk への適用、stderr 記録。
- `engine/src/program/generate.cpp:4033,6830,18864-18865,18925,18943,20769-20809` — CLI 設定、server request 上書き、segment 計画。
- `docs/SETTINGS.md:264`, `docs/MULTI_GPU.md:151` — 対応 backend 表記と機能の概要。

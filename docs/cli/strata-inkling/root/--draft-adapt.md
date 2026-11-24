# `strata-inkling --draft-adapt`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（CUDA/HIP root parser） |
| オプション | `--draft-adapt` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

serve モードで DSpark speculative decoding の実測利得を見て、利得が低いときに一時的に通常の 1 token decode に切り替える適応制御を有効にします。フラグだけでは drafter を有効化せず、モデルに DSpark があり backend が利用可能であることも必要です。

## 使い方

```sh
strata-inkling --serve --native ./model.strata --draft-adapt
```

`--draft-adapt` 自体は値を取らず、モデル指定や serve モードは別途必要です。

## 値と既定値

フラグ指定時に `cfg.bopts.spec_adapt = true` となります。値の変換や範囲検証はなく、`--draft-adapt` の直後の引数をこのフラグの値として消費しません。省略時は `spec_adapt` が false のままです。同じフラグを複数回指定しても true を再設定するだけです（`engine/src/inkling2/ink_main.cpp:902-904`、`engine/src/inkling2/ink_backend.h:40`）。

## 実行時の動作

`--serve` で起動した共通 serve loop は、`--draft` が `off` でなく、モデルに DSpark 情報があり、backend の初期化も済んでいる場合に `use_dspark` を true にします。適応制御は `--draft-adapt` または環境変数 `STRATA_INK_SPEC=adapt` のどちらかで有効になります（`engine/src/inkling2/ink_serve.h:507-514`）。従って `--draft off`、DSpark 非搭載モデル、backend 非対応・初期化失敗の場合は、このフラグがあっても speculative decoding の適応切替は実行されません。

初回の適応対象リクエストでは、通常 decode の最初の 4 decode step を校正に使います。serve loop は single active request の通常 decode step の所要時間を測り、初期校正後は通常 step の時間を指数平滑で更新します（`engine/src/inkling2/ink_serve.h:734-735,1218-1228`）。Speculative step ごとに出力 token 数と所要時間を集計し、12 step ごとに `平均出力 token/step ÷ (平滑化 speculative step 時間 / 通常 step 時間)` を利得として算出します。利得の平滑値が `0.93` 未満になると、その request は 40 通常 step の間 speculative fast path を通らず、その後再び試行します（`engine/src/inkling2/ink_serve.h:517-528,876-880`）。

この制御は single active request かつ speculative DSpark path が使える場合に適用されます。並列処理中など条件を満たさない場合は観測・切替処理の対象になりません。通常の greedy tree path と block rejection-sampling path の両方で speculative step の計測が行われます（`engine/src/inkling2/ink_serve.h:882-897,965-995,1218`）。`STRATA_INK_SPEC=block` は tree ではなく block drafter を選ぶ既存の測定スイッチで、`adapt` 有効化とは別の設定です（`engine/src/inkling2/ink_serve.h:508-514`）。

## 適用条件と副作用

このフラグが変えるのは serve loop 内の decode 経路選択です。Speculative step の実測利得が閾値を割ると最大 40 decode step の間 drafter を使わず、以降に再評価します。request ごとに窓の集計状態を初期化しますが、通常 step 時間の校正値は serve loop 内で共有されます（`engine/src/inkling2/ink_serve.h:515-528,734-735`）。設定ファイルへの書き込みやフラグ専用のファイル・ネットワーク副作用は確認できません。

## 出力とエラー

このフラグ専用の標準出力・標準エラー出力はありません。値なしのフラグとして parser が受理します。未知のオプションは `unknown option: ...` を stderr に出して終了コード 2、モデル指定がなければ `--native ... is required` を stderr に出して終了コード 2 です（`engine/src/inkling2/ink_main.cpp:845-849,902-904,985-987,1073-1075`）。serve 起動時のモデル open または backend 初期化失敗は protocol error を出して終了コード 1 になります（`engine/src/inkling2/ink_main.cpp:1078-1095`）。

## 根拠

- `engine/src/inkling2/ink_main.cpp:902-904` — root parser が値なしで `spec_adapt` を true にする。
- `engine/src/inkling2/ink_backend.h:40` — 設定の既定値は false。コメントにも閾値と 40 step の概要がある。
- `engine/src/inkling2/ink_serve.h:507-528` — DSpark の利用条件、環境変数による有効化、12 step 集計と利得閾値・停止期間。
- `engine/src/inkling2/ink_serve.h:734-735,876-880,1218-1228` — request 初期化、適応時の fast path 抑止、通常 step の校正・更新。
- `engine/src/inkling2/ink_serve.h:882-897,965-995` — tree / block の speculative step が適応計測へ渡る箇所。
- `engine/src/inkling2/ink_main.cpp:985-987,1073-1095` — parser の未知引数、および model/backend 起動失敗経路。

本調査では実行バイナリの help 表示や実行は行っていません。Indexed CUDA/HIP entrypoint の parser と共通 serve loop のソースを確認しました。

# `STRATA_SPEC_ADAPT_SM86`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

## 役割

CUDA compute capability 8.6（sm_86）で speculative decoding 時の適応 expert tier の開始時設定を opt-in で変更します。有効になると、利用者が別途設定していない場合に `STRATA_SPEC_ADAPT_EVERY=2` と `STRATA_SPEC_ADAPT_WARM=200` をプロセス環境へ設定します。これは speculative round の最初の warm-up 区間で expert 入れ替え間隔を短くするための値です。通常の sm_86 exact speed switches の既定有効化とは別の設定です。

## 値と判定

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（設定ありでも先頭文字は `\0`） |
| 先頭文字が `1` | 有効。`1`, `10`, `1anything` を含む |
| その他 | 無効。`0`, `true`, ` 1` など |

文字列全体や数値としての妥当性、大文字小文字は検査しません。先頭文字だけを比較します。

## 有効になる条件

- CUDA の初期化経路で、可視な全 GPU の compute capability が同一であること。GPU がない、属性取得に失敗する、または capability が混在する場合はこの設定関数が呼ばれません。
- その capability が 8.6 であること。他の世代では無効です。
- `STRATA_SM86_PERF` の先頭文字が `0` ではないこと。未設定・空文字を含むそれ以外の値は通過します。先頭文字 `0` ならこの opt-in を止めます。

ビルドが HIP または Metal の場合、この CUDA 専用処理はコンパイル対象外です。

## 実行時の詳細

CUDA デバイス情報を集める初期化時に `apply_spec_adapt_default()` が一度呼ばれ、そこで環境を読みます。変数が有効でも、デフォルトは設定しません。条件を満たした場合に、`STRATA_SPEC_ADAPT_EVERY` または `STRATA_SPEC_ADAPT_WARM` が未設定のものだけ、それぞれ `2` と `200` に設定します。値が空文字でも「設定済み」として保持されます。値の設定に関するログはこの関数にはありません。

後続の speculative decoding 設定では `--spec >= 2` かつ `--adapt-every` が明示されていない場合に限り、両変数を `atoi` / `atoll` で読みます。`EVERY` が正で通常の `adapt_every` より小さく、`WARM` が正なら、最初の `WARM` rounds に限り interval を `EVERY` にします。いずれかの数値条件を満たさない場合は warm-up interval を設定しません。`--adapt-every` が明示された場合はこの経路を使いません。従って、この環境変数単体では speculative decoding の適応や interval を有効化せず、他の指定や通常の `adapt_every` が必要です。

ユーザーが `STRATA_SPEC_ADAPT_EVERY` / `STRATA_SPEC_ADAPT_WARM` を空文字や不正値で設定していた場合も、初期化は上書きしません。後段の整数変換結果が正でなければ warm-up 設定は適用されません。

## 根拠

- `src/program/generate.cpp:2838-2853`: CUDA ビルドで可視 GPU の capability 一致を確認後に初期化関数を呼び出す。
- `src/core/nv_defaults.cpp:73-92`: sm_86 判定、環境変数の先頭文字判定、`STRATA_SM86_PERF` による抑止、および未設定の warm-up 変数への既定値設定。
- `src/program/generate.cpp:3220-3230`: speculative decoding の条件、CLI 指定の優先、数値変換、warm-up interval の適用。
- `include/strata/core/nv_defaults.hpp:34-38`: この設定が sm_86 向け opt-in である旨。

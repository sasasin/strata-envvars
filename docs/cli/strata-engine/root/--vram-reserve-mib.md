# `strata generate --vram-reserve-mib`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate`（エンジン引数） |
| オプション | `--vram-reserve-mib` |
| 別名 | なし |
| 値 | MiB 単位の整数。引数なしの既定値は 700 MiB |

## 役割

GPU 上でモデルを実行するとき、ExpertCache などの割り当てに使わず空けておく VRAM 量を指定します。特に `--expert-cache auto` の容量計算では、重み・セッション等を読み込んだ後の空き容量から予約量と他の見積もり分を差し引き、残りをキャッシュ容量にします。予約を増やすとキャッシュに使える量が減り、予約を減らすと増えます。予約量は VRAM 全体の制限ではなく、エンジンが他の処理用に確保する空きの目安です（`engine/src/program/generate.cpp:958-961, 9001-9005, 9130-9155`）。

## 使い方

```sh
# 例: pack のモデルを使い、ExpertCache などに割り当てない VRAM を 1200 MiB として実行する
strata generate --pack ./pack --tokens "1,2,3" --vram-reserve-mib 1200
```

これはエンジンの実行例です。`--pack` と `--tokens` を含む呼び出し形式は `engine/src/program/generate.cpp:1206-1212` にあります。

## 値と既定値

- 値は `std::atoi` で `int` に変換され、初期値は 700 です。範囲・非負条件を検査する validation はこの parser にありません。数値でない文字列は `atoi` により 0 になり、複数回指定時は引数走査で後に指定した値がフィールドに残ります（`engine/src/program/generate.cpp:960-961, 3837-3842, 3992`）。
- 値を省略すると parser の既定値 700 MiB が使われます。オプション名の後に値そのものがない場合は stderr に `<option> needs a value` を出して終了コード 2 で終了します（`engine/src/program/generate.cpp:3839-3842`）。
- 負数を含む不正・極端な値の安全な意味はソースから確認できません。VRAM 計算で MiB 値をバイト換算・符号なし型へ変換する箇所があるため、非負の整数を指定してください（例: `engine/src/program/generate.cpp:9130, 9378-9380`）。

## 実行時の動作

- `--expert-cache auto` では、空き VRAM から予約量、prompt 用バッファ、draft head、pipeline window などの見積もり分を差し引いて ExpertCache の slot 数を決めます。起動後の実割り当てで空きが不足すると、自動 cache は縮小を試み、ログに縮小内容を出します（`engine/src/program/generate.cpp:8988-9005, 9130-9155, 9612-9632`、共通計算 `engine/include/strata/core/auto_cache.hpp:30-44`）。
- 明示値は `vram_reserve_given` に記録されます。これにより通常の自動 reserve 調整から区別されます。たとえば低 VRAM の離散 GPU で既定 reserve を 480/550 MiB に下げる自動規則は、明示指定または既定値以外の reserve には適用されません（`engine/src/program/generate.cpp:3992, 9102-9115`、`engine/include/strata/core/low_vram_rules.hpp:84-91`）。
- `--expert-cache auto` で作業可能な最小 cache を確保できない場合、明示指定がない構成では reserve を下げる調整があり、別の不足時処理では prompt chunk を小さくするなどして起動可能性を探ります。明示値があると一部の自動調整は抑止され、VRAM が足りない場合に cache 不足の診断が出ます（`engine/src/program/generate.cpp:9220-9241, 9243-9271, 9325-9345`）。
- 明示した ExpertCache 容量も reserve と空き量に影響されます。たとえば layer split では、指定 slot 数が予約量などを残した容量を超えると警告を出し、slot 数を収まる値に切り詰めます（`engine/src/program/generate.cpp:9347-9363`）。

## 適用条件と副作用

- 予約量を使う cache の算定は GPU の空き容量を取得する実行経路で行われます。OS、GPU backend、cache の指定方法、モデル構成に応じて見積もりや補正の分岐が異なります。SYCL 実装にも同じ parser と 700 MiB の既定値があり、自動 cache の容量から reserve を差し引きます（`engine/sycl/src/program/generate.cpp:626-629, 2015, 4875-4882`）。
- Windows の WDDM 離散 GPU では、CUDA/HIP 側の実装がデバイス容量などに応じて安全余裕を引き上げる場合があります。Windows の HIP 自動 cache では、条件に合う未指定の reserve を 2560 MiB に引き上げます。Windows WDDM の規則は `STRATA_WDDM_VRAM_FLOOR=0` で無効化できます。これらは自動 cache の経路に限った処理で、OS・GPU の判定条件を満たさない場合は適用されません（`engine/src/program/generate.cpp:9014-9043, 9083-9100`、`engine/include/strata/core/low_vram_rules.hpp:37-73`）。
- 予約を増やすと ExpertCache に保持できる expert が減り、RAM/SSD 側から読む量が増える構成では実行が遅くなることがあります。ソースは不足時に cache を小さくして起動を続ける経路を示していますが、性能への具体的な変化量はここでは測定していません（`engine/src/program/generate.cpp:9220-9269`）。

## 出力とエラー

- 自動 reserve の変更、見積もり結果、割り当て後の不足と cache 縮小は `strata generate:` で stderr に出力されます（例: `engine/src/program/generate.cpp:9031-9036, 9107-9111, 9173-9176, 9628-9632`）。
- 最小の ExpertCache を確保できない場合は、必要 slot 数や不足量、容量を空ける案内を stderr に出します（`engine/src/program/generate.cpp:9338-9345`）。cache の割り当て自体に失敗し、自動縮小でも回復しない場合はエラーを stderr に出して終了コード 1 で戻ります（`engine/src/program/generate.cpp:9582-9610`）。
- parser が値の範囲を検証しないため、範囲外値に対する専用エラーは確認できません。上記の負数・極端な値について、定義されない変換や後続の算定結果は記述していません。

## 根拠

- `engine/src/program/generate.cpp:958-961` — reserve の説明、既定値、明示指定フラグ。
- `engine/src/program/generate.cpp:3837-3842, 3992-3994` — 引数走査、必須値の扱い、parser の数値変換。
- `engine/src/program/generate.cpp:9001-9050, 9070-9116, 9130-9155` — CUDA/HIP/Metal 共通ソースの空き VRAM 見積もりと OS/GPU 条件別の調整。
- `engine/src/program/generate.cpp:9220-9363, 9373-9410` — cache 不足時の再調整、layer split と明示 cache の容量計算。
- `engine/src/program/generate.cpp:9582-9637` — cache 割り当ての失敗・再試行・stderr 出力。
- `engine/sycl/src/program/generate.cpp:626-629, 2015, 4875-4909, 5002-5024` — SYCL の parser、予約量を使う自動容量計算、および不足時の調整。
- `engine/include/strata/core/auto_cache.hpp:30-44` — 自動 cache slot 数の計算式。
- `engine/include/strata/core/low_vram_rules.hpp:37-73, 84-91` — WDDM と低 VRAM GPU の自動 reserve 規則。

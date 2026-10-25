# `STRATA_VERIFY_COMPLEMENT`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

テスト・診断用のチェックサム出力を有効にします。CUDA の expert cache complement を常駐 RAM に構築した後、そのホスト側データと配置 offset からチェックサムを出力します。また `strata generate` のプロファイル事前投入経路では、GPU cache の各 resident slot をホストへ読み戻したチェックサムを出力します。名前に `VERIFY` とありますが、これらのチェックサムを期待値と比較して成否を判定する処理ではありません。

## 値と判定

両方の参照箇所で `std::getenv("STRATA_VERIFY_COMPLEMENT") != nullptr` を使います。文字列の内容は parse しません。

| 値 | 動作 |
|---|---|
| 未設定 | この変数によるチェックサム計算・出力をしない |
| 空文字を含む任意の設定値 | チェックサム計算・出力を有効にする |

`0`、`false`、空文字も「設定済み」なので有効です。判定は処理箇所に到達したときに行われ、結果の static cache はありません。

## 有効になる条件

- 常駐 complement 側は、`FileExpertSource::pin_cache_complement()` が正常に構築を終え、`host != nullptr` かつ `bytes > 0` の場合にチェックサムを計算します。resident RAM mode が呼び出されない実行ではこの処理もありません。
- generate 側は、GPU expert cache のプロファイル事前投入ブロック（`profile` が空でなく `srcp != nullptr`）を通り、事前投入処理の後に到達した場合にスロットを読み戻します。空のプロファイルなど、このブロックを通らない経路では動作しません。
- いずれも Strata の CUDA 実装にある経路です。

## 実行時の詳細

常駐 complement 側では、`bytes` を最大 1 GiB の連続区間に分け、最大8本の CPU worker で各区間の FNV-1a 64-bit hash を計算します。各区間 hash を並べた配列と `offsets` 配列も FNV-1a で集約し、stderr に `FileExpertSource: cache complement checksum ...` とサイズを出します。これは complement の構築完了後に一度実行されます。

generate 側では、resident slot を layer/expert 全体から列挙して slot 番号でソートし、最大8本の worker で各 GPU slot の blob を `cudaMemcpy(..., cudaMemcpyDeviceToHost)` により読み戻します。各 blob の FNV-1a hash と slot 番号・blob byte 数を slot 順に集約し、stderr に `strata generate: expert cache checksum ...` と slot 数を出します。読み戻し失敗が一つでもあると末尾に `A READ-BACK FAILED` を付けますが、この分岐はその失敗で処理を中断せず、hash 値も出力します。

両経路ともチェックサムを相互比較したり、期待値との不一致でエラーにしたりはしません。環境変数が変えるのは追加の CPU hash 計算、GPU からの読み戻し、および診断ログです。

## 根拠

- `src/core/expert_source.cpp:2634-2649,3182-3200,3216-3221` — complement 構築関数、チェック条件、1 GiB 単位の host hash と offsets を含む集約、stderr 出力。
- `src/program/generate.cpp:5455-5465,5502-5517,5517-5549` — プロファイル事前投入の適用範囲、通常の slot 検証後に環境変数を確認する位置、GPU slot の読み戻し・集約・失敗ログ。
- `docs/DETAILS.md` に `STRATA_VERIFY_COMPLEMENT` の説明やチェックサム照合仕様は見つかりませんでした。

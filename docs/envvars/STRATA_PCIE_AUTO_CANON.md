# `STRATA_PCIE_AUTO_CANON`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Windows の CUDA ビルドで、canonical Q2_0 pack の PCIe share を起動時の既定値から自動調整するための PCIe 帯域 probe を有効にする。通常は canonical pack の probe を行わず `pcie_frac` の既定値を使うが、この変数が有効なら probe に成功したとき `PcieAuto` が CPU pool の実測速度も使って share を後続の decode window で更新する。native pack の probe や HIP の既定動作を切り替える変数ではない（`engine/src/program/generate.cpp:5535-5555,5560-5565,14908-14930`）。

share は各層の未キャッシュ expert のうち PCIe 経由で処理する割合で、残りを CPU pool が処理する（`engine/src/program/generate.cpp:1039-1043`）。値の変更は処理分担を変える。ソースは分担差で丸めが変わり得ると説明しており、出力 token が同一になる保証は確認できない（`engine/src/program/generate.cpp:15043-15046`）。

## 値と判定

読み取りは `std::getenv` で得た文字列の先頭 1 byte が ASCII `'1'` かだけを見る。文字列全体の parse や真偽値変換はしない。未設定・空文字は無効。`1`、`1x`、`10` は有効で、`0`、`true`、` 1`、`01`、`1` 以外の先頭文字を持つ値は無効。大文字小文字や数値としての妥当性を検査しない（`engine/src/program/generate.cpp:5544-5549`）。

| ビルド／条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Windows CUDA（`!STRATA_USE_HIP && _WIN32`）、`--pcie-frac` 未指定、canonical pack | probe しない。canonical pack の base share（通常 `0.2`）を使う | 先頭 byte が `1`。probe を試みる | 空文字、`0`、`true`、先頭 byte が `1` 以外。probe を試みない |
| Windows CUDA でも `STRATA_PCIE_FRAC_DEFAULT=old` | probe しない | この変数が有効でも `old` が優先し probe しない | 同左 |
| 非 Windows CUDA または HIP | この変数は参照されず、動作に影響しない | 該当なし | 該当なし |

`STRATA_PCIE_FRAC_DEFAULT` は値が完全一致で `old` のときだけ `old` 扱いになる。空文字や `OLD` は `old` ではない（`engine/src/program/generate.cpp:5538-5549`）。

## 有効になる条件

- Windows かつ CUDA ビルドであること。HIP ビルドでは別分岐となり、canonical pack の probe は無効。Linux 等の CUDA ビルドではこの変数を読み取らず、canonical pack の probe は `STRATA_PCIE_FRAC_DEFAULT=old` でない限り試みる（`engine/src/program/generate.cpp:5544-5555`）。
- `--pcie-frac` を省略し、内部値 `o.pcie_frac` が負のままであること。`--pcie-frac` の値は `std::atof` で設定され、0 以上なら環境変数を読む分岐全体を飛ばす。したがって明示値が優先する（`engine/src/program/generate.cpp:4057,5535`）。
- `--pack` の expert layout が native ではない canonical Q2_0 pack であること。この変数は native pack に対する probe 条件には使われない（`engine/src/program/generate.cpp:5445,5555-5576,5598-5602`）。
- `STRATA_PCIE_FRAC_DEFAULT=old` が指定されていないこと。`old` の場合、Windows CUDA ではこの変数が `1` でも canonical probe は抑止される（`engine/src/program/generate.cpp:5538-5555`）。
- probe が正の帯域値を返すこと。probe が失敗すると base share を使い、自動調整用の帯域値は設定されない（`engine/src/program/generate.cpp:5555-5579`）。
- decode 中の自動更新には、さらに全 expert が host 側に resident ではないこと、`--batch` が 0、`--peer-device` が未指定であることが必要。これらを満たさない場合 `PcieAuto` は起動しない（`engine/src/program/generate.cpp:14931-15010`）。

## 実行時の詳細

変数は `generate.cpp` の PCIe share 初期化時に一度読み、static cache には保存しない。プロセス起動後に環境を変更しても、既に選択した probe 経路には反映されない（`engine/src/program/generate.cpp:5535-5555`）。`--pcie-frac` 未指定の Windows CUDA canonical pack では、値が有効で `STRATA_PCIE_FRAC_DEFAULT` が `old` でなければ、1 GiB の host-to-device copy を 256 MiB の 4 burst で測り、最も高い帯域値を使う。probe の host/device allocation や測定に失敗した場合は負値が返り、自動更新は始まらない（`engine/src/program/generate.cpp:2915-2983,5555-5579`）。

probe 成功時、canonical pack の開始 share は base のまま設定され、非 HIP ビルドでは `pcie_frac_auto` と probe 帯域値が保存される。layer split があるとこの canonical pack 経路では自動更新を有効にしない（`engine/src/program/generate.cpp:5558-5565`）。その後、条件を満たす場合は decode window の miss 数と CPU pool の実行時間を集計し、最初の判定は12 window後、以降は48 window単位で最大3回更新する。集計対象の miss が300未満なら次の集計を待ち、合計2000 windowまでその状態なら自動調整を停止する。更新候補はリンク帯域と pool 速度から計算され、0.05刻みに丸められ、下限0.10と `pcie_share_max()` の上限内に制限される（`engine/src/program/generate.cpp:3117-3150,15003-15041`）。

## ログと測定値

probe 成功時は stderr に `strata generate: PCIe probe: %.1f GB/s host->device (best of %s); the canonical pack starts at pcie_frac %.2f and refines it from the CPU pool's speed` を出す。失敗時は `strata generate: PCIe probe failed -> pcie_frac default %.2f` を出す。値が無効、対象外の OS/backend/pack、または `--pcie-frac` 指定により probe 分岐へ入らない場合、この probe 用メッセージは出ない（`engine/src/program/generate.cpp:5555-5579`）。

自動更新が share を変更すると stderr に `strata serve: PCIe share: the CPU pool takes ...` の行が出る。開始時に `STRATA_PCIE_START` が CUDA の新しい start 値を選ぶ場合は `strata serve: PCIe share: start ...` も出る。更新は最大3回で、候補値が現在値との差 0.025 未満なら変更ログを出さない（`engine/src/program/generate.cpp:14913-14929,15015-15029,3127-3149`）。

ソースコメントは Windows の RTX 5070・canonical Q2_0 について、短い回答で 3% 遅く、コードで 2.5% 速かったと報告する（`engine/src/program/generate.cpp:5545`）。`docs/DETAILS.md:1706` も Windows の RTX 5070 canonical Q2_0 を含む測定として code `+2.5%`、short answer `-3.3%` を記載する。記述は試験条件付きの報告値であり、この変数の一般的な性能効果を示すものではない。`docs/SETTINGS.md:202` の「on / off」「NVIDIA and AMD」という一覧表示は実装の限定（Windows CUDA のみ）を表していないため、実装条件を優先する。

## 根拠

- 候補名の実読み取り、文字判定、build 条件: `engine/src/program/generate.cpp:5535-5555`
- CLI 優先順位、pack 判定、probe 成否と初期 share: `engine/src/program/generate.cpp:4057,5445,5535-5579`
- probe 実装と失敗値: `engine/src/program/generate.cpp:2915-2983`
- `PcieAuto` の有効条件、観測、更新上限: `engine/src/program/generate.cpp:14931-15041,3117-3150`
- 比較した設定表・測定記録: `docs/SETTINGS.md:202`, `docs/DETAILS.md:1706`

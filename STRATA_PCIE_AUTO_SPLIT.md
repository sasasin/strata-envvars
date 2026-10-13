# `STRATA_PCIE_AUTO_SPLIT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

サーバーの layer split で、各 GPU の PCIe 帯域と CPU expert pool の処理速度を使い、各 stage の `pcie_frac` を decode 中に自動調整する経路を許可します。分担率は、VRAM にない expert のうち PCIe 経由で GPU に送る割合です。この変数自体は率を指定せず、`--pcie-frac` の未指定時に働く自動調整の許可フラグです。

変数を読むのは `src/program/generate.cpp` の `pcie_auto_split_ok()` だけです。結果は関数内の `static const bool` に保存されるため、最初の呼び出し以降に環境変数を変更してもプロセス内では反映されません。コード上この判定に HIP 専用の compile guard はありません。資料は HIP の opt-in 機能として説明していますが、判定式自体は CUDA/HIP 共通コードです。

## 値と判定

値全体の検証ではなく `std::atoi()` の結果が 0 かどうかで判定します。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字、数値変換できない文字列（例: `true`） | `atoi` が 0 を返すため無効 |
| 先頭の空白と符号の後に 0 以外の整数がある文字列（例: `1`, `-1`, `2foo`) | 有効 |
| 変換される整数が 0 の文字列（例: `0`, `+0`, `0foo`) | 無効 |

`atoi` は整数の後ろに続く文字を検査せず、数値でない末尾や大文字小文字も個別には検査しません。変換可能な数値の範囲チェックもありません。したがって推奨値 `1` 以外でも、`atoi` の結果が非ゼロなら許可フラグは有効です。根拠: `src/program/generate.cpp:1564-1567`。

## 有効になる条件

この値が有効でも、自動調整が動くのは次の条件を満たす場合です。

- `--pcie-frac` が未指定で、起動時の PCIe probe が成功し、`o.pcie_frac_auto` が有効になること。明示した `--pcie-frac` はこの初期化を迂回します。
- HIP では native pack を使うこと。この環境変数による split 許可は `native_pack` 側の初期化で設定されます。CUDA の canonical Q2_0 pack は別分岐で、layer split 時はこの環境変数を設定しても `pcie_frac_auto` が有効になりません。
- GPU が `decode_defaults_arch_ok()` を通ること。HIP では GPU の `gcnArchName` が gfx1200 または gfx1201 の場合だけ通ります。CUDA ではこの判定は常に true です。
- `STRATA_PCIE_FRAC_DEFAULT=old` でないこと。これは `strcmp` による文字列全体の完全一致で、`old` のとき自動調整を無効にします。
- expert がすべて GPU に常駐しておらず、`--batch` が 0、`--peer-device` が未指定であること。
- layer split でこの経路を有効にする場合は、`STRATA_PCIE_AUTO_SPLIT` が有効であること。layer split がない場合、split 許可フラグは条件になりません。
- 自動更新を処理する通常の serial decode loop を通ること。pipeline decode が実行された window ではこの更新箇所を通りません。

初期化と利用条件の根拠: `src/program/generate.cpp:1569-1579,2736-2772,8241-8249`。`--pcie-frac` の判定根拠: `src/program/generate.cpp:2255-2257`。

## 実行時の詳細

初期 PCIe probe は起動時に実行されます。native pack では、各 stage が自身の host-to-device 帯域を probe し、その結果を `link_gbps` と初期の `pcie_frac` に保存します（probe に失敗した stage は率の再計算に使える帯域値を持ちません）。probe された帯域が 20 GB/s 未満なら初期率は基準率に比例して下がり、20 GB/s 以上なら基準率を保ちます。native pack の基準率は 0.55 です。根拠: `src/program/generate.cpp:1651-1658,3469-3479`。

自動調整は要求ごとの prompt window を除外し、decode の各 window で CPU pool の累積実行時間と missed expert 数を観測します。最初は 48 window、その後は最大 96 window ごとに評価し、累積 missed expert 数が 300 未満なら読み取りを先送りします。2000 window まで十分な miss がなければ自動調整を止めます。CPU pool の expert bytes/s とリンク帯域から率を算出し、0.05 刻みに丸めて 0.10〜0.60 に制限します。初回を含め最大 3 回更新します。新しい率が現在値と少なくとも 0.025 異なるときにだけ更新し、stderr に `PCIe share:` 行を出します。更新対象は既定率の request であり、request が独自の率を指定している場合は変更しません。根拠: `src/program/generate.cpp:1660-1700,11981-12005`。

layer split では、先頭 GPU の率を CPU pool の測定値と先頭 GPU の probe 帯域から更新し、後続 stage は同じ CPU pool 速度とそれぞれの probe 帯域から個別に再計算します。後続 stage の probe が失敗して帯域が正でない場合、その stage の率はこの更新では変更されません。3 stage 以上でも許可判定はありますが、pipelined decode が動いている間はこの serial loop の率更新を実行しません。根拠: `src/program/generate.cpp:8241-8249,11981-12005`。

## 文書との照合・測定値

`docs/DETAILS.md:1652-1653` は、HIP の `STRATA_PCIE_AUTO_SPLIT=1` により二段 layer split の率を各 stage のリンク帯域に合わせて調整すると説明しています。資料の測定条件は 2 枚の R9700、16 GB 相当、tail skip 有効で、Q2_0 は story +4.5%、code +9.9%、4K +8.8%、IQ3_S は story -2.1%、code +8.0%、4K +23.3% です。3 stage 以上では pipelined loop がこの調整を実行しないとも記載されています。これらは資料にある測定条件と数値であり、この調査で再測定していません。

資料は HIP の opt-in としています。一方、`pcie_auto_split_ok()` の定義・呼び出しに backend guard はなく、native pack の共有コードでは CUDA でもこの変数が split 時の自動調整許可に使われます。CUDA での split 構成について、上記資料にこの環境変数を使った測定値は記載されていません。CUDA canonical Q2_0 pack は前述の別分岐で split 時の自動調整対象外です。

## 根拠

- `src/program/generate.cpp:1563-1567` — 環境変数の唯一の読み取り、`atoi` 判定、static cache。
- `src/program/generate.cpp:1569-1579,2736-2772` — backend/architecture 条件、起動時 probe、率自動調整の初期化。
- `src/program/generate.cpp:8241-8249,11981-12005` — all-resident/batch/peer 条件と decode 中の率更新。
- `src/program/generate.cpp:1660-1700,3469-3479` — pool 測定スケジュール、率の計算、stage 別リンク probe。
- `docs/DETAILS.md:1642-1653` — 機能説明と資料記載の測定条件。

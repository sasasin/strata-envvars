# `STRATA_PCIE_FRAC_DEFAULT`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

expert cache miss の PCIe share (`pcie_frac`) に使う起動時の既定動作を選びます。値が文字列として厳密に `old` の場合、canonical Q2_0 pack で新しい自動調整用プローブを使わず、serve 中の `PcieAuto` による share の更新も止めます。これは `--pcie-frac` の代替ではなく、明示的な `--pcie-frac` が優先します。

share は miss のうち GPU 側で PCIe 経由に扱う部分を決めます。実装は `pcie_frac * 256` を丸めて 0〜256 に制限した `pcie_num` として verifier に渡し、verifier はその share の expert rows を GPU 側で処理します。CPU pool 側に残る miss の計算・転送と分担する設定です。

## 値と判定

`std::getenv()` の結果を `std::strcmp(pfd, "old") == 0` で比較します。数値変換や真偽値 parse はありません。

| 環境変数の状態 | `pf_old` |
|---|---:|
| unset | false |
| 空文字 | false |
| 完全一致で `old` | true |
| `OLD`, `old `, `older`, `1` など、それ以外の文字列 | false |

大文字小文字、空白、接尾辞を含めて完全一致だけが有効です。変数は既定 share を設定する箇所で読み取られ、値を static cache しません。通常の起動ではこの設定箇所は一度通ります。

## 有効になる条件

- `--pcie-frac` が省略されたか、parse 結果が 0 未満の場合にだけ環境変数が参照されます。0 以上の `--pcie-frac` では既定 share の処理全体を通らず、環境変数は読まれません。CLI の値は `std::atof()` で変換され、`pcie_num` 作成時に 0〜256 の範囲へ制限されます。
- canonical pack（`native_pack == false`）の CUDA では、`old` は PCIe probe と serve 中の自動調整を抑え、開始 share 0.2 を使います。Linux CUDA で unset または `old` 以外なら probe を試します。probe 成功時も canonical pack の開始値は 0.2 で、対応する serve 経路では `PcieAuto` が CPU pool の実測に応じて後から share を調整します。probe 失敗時は 0.2 のままです。
- Windows CUDA の canonical pack は `STRATA_PCIE_AUTO_CANON` も条件になります。同変数の先頭文字が `1` で、かつ `STRATA_PCIE_FRAC_DEFAULT` が `old` でない場合に限って probe します。`STRATA_PCIE_FRAC_DEFAULT=old` はこの opt-in より優先します。
- HIP の canonical pack は probe/autotune の対象外で、開始値 0.2 を使います。`STRATA_PCIE_FRAC_DEFAULT` を `old` 以外にしてもこの canonical pack の probe は有効になりません。
- native pack は backend にかかわらず `native_pack` の条件で PCIe probe を試します。成功すれば開始 share は base 0.55 を probe 帯域に応じて縮小し、失敗すれば 0.55 です。この native-pack の起動時 share は `STRATA_PCIE_FRAC_DEFAULT=old` でも変わりませんが、`old` は後述する `PcieAuto` による serve 中の更新を抑えます。
- probe 後の `PcieAuto` は serve の非 resident expert cache 経路でのみ候補になります。batch 指定、peer GPU、全 expert が VRAM resident の場合は実行されません。layer split では CUDA は通常無効で、HIP は `STRATA_PCIE_AUTO_SPLIT` が `atoi` で非ゼロとなる場合に限り対象になり得ます。HIP の自動調整は `decode_defaults_arch_ok()` が true の gfx12 WMMA 世代（gfx1200/gfx1201）に限られます。いずれも `old` なら初期更新設定が無効になります。

## 実行時の詳細

既定 share の設定は `o.pcie_frac < 0.0` のとき `generate.cpp` で行われます。CUDA/Linux の canonical pack では probe に成功しても起動 share を 0.2 に保ち、probe 値を記録します。serve 側で `PcieAuto` が有効な場合、最初は 48 decode windows、その後は 96 windows ごとに miss 数と実行時間を集計します。十分な miss があり、pool 速度を算出できると、link 帯域と CPU pool 速度から share を 0.05 刻みで再計算します。変更があれば stderr に `strata serve: PCIe share: ...` と出し、次の処理に使う `pcie_num` を更新します。最大3回の更新です。

したがって `old` の効果は「常に固定値 0.2」ではありません。これは主に canonical pack の CUDA で旧来の起動ルールを選ぶ値です。native pack は起動 probe による帯域補正を引き続き行い、CLI で明示 share があればそれを優先します。

## 文書との照合

`docs/DETAILS.md` は `STRATA_PCIE_FRAC_DEFAULT=old` を 0.1.41 ルールの維持手段として説明し、canonical Q2_0 pack の新しい既定と比較した測定を記載しています（`docs/DETAILS.md:1652-1666`）。この文書では測定値を再検証していません。コード上では pack/backend により `old` の作用範囲が異なり、native pack の起動 probe は止めず `PcieAuto` の更新だけを止める点を補足しています。

## 根拠

- `src/program/generate.cpp:575-577`: PCIe share と自動調整状態の初期値。
- `src/program/generate.cpp:1563-1579`: HIP layer-split opt-in と gfx12 判定。
- `src/program/generate.cpp:1651-1699`: 帯域による share 計算と `PcieAuto` の更新間隔・範囲。
- `src/program/generate.cpp:1996`: `--pcie-frac` の parse。
- `src/program/generate.cpp:2255-2257`: 明示 share 判定。
- `src/program/generate.cpp:2731-2772`: 環境変数の完全一致判定、pack/backend 別 probe、開始 share と自動調整フラグ。
- `src/program/generate.cpp:8200-8201,8241-8249`: share の verifier 値への変換と自動調整の適用条件。
- `src/program/generate.cpp:11981-12004`: serve 中の調整、ログ、share の更新。
- `src/core/verify.cpp:1610-1640`: PCIe share と CPU 側 miss rows の実行・転送経路。
- `docs/DETAILS.md:1652-1666`: 文書上の既定説明と測定条件。

# `STRATA_PCIE_AUTO_SPLIT`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。外部ライブラリの環境変数は対象外。

## 役割

PCIe 経由で GPU に送る expert の割合（`pcie_frac`）を、CPU pool の実測速度から自動調整する機能を、layer split 実行時にも許可する opt-in 変数です。layer split では後段 GPU の PCIe link 速度も使い、各 stage の割合を個別に更新します。

この変数自体が `pcie_frac` を直接指定するわけではありません。起動時に自動調整が有効になり、expert の cache miss など他の条件を満たす場合にのみ作用します。

## 値と判定

値は `std::atoi` で整数変換し、変換結果が 0 以外なら ON です。文字列全体の厳密な検証はありません。

| 値 | 結果 |
| --- | --- |
| 未設定 | OFF |
| 空文字、`0`、`false`、整数として 0 に変換される文字列 | OFF |
| `1`、`-1`、`2`、`1tail` など、`atoi` の結果が 0 以外 | ON |

先頭空白や符号は `atoi` の規則で扱われます。例えば `" 1x"` は 1 に変換されて ON、`"true"` は 0 に変換されて OFF です。環境変数の値は `pcie_auto_split_ok()` 内の関数 static に保存され、最初の評価後にプロセス内で値を変更しても再評価されません。根拠: `src/program/generate.cpp:1622-1626`。

## 有効になる条件

- 起動時の `--pcie-frac` が指定されていないこと。指定時はその割合を使い、起動時の PCIe probe と自動調整の設定経路に入りません。
- probe が成功すること。probe に失敗すると基準割合を使い、自動調整は設定されません。
- `STRATA_PCIE_FRAC_DEFAULT=old` でないこと。
- 全 expert が GPU resident でなく、`--batch` を使わず、`--peer-device` を使っていないこと。
- layer split の場合は `STRATA_PCIE_AUTO_SPLIT` が ON であること。単一 GPU の場合、この変数は自動調整の許可条件になりません。
- HIP では `decode_defaults_arch_ok()` が gfx1200 または gfx1201 と判定すること。CUDA ではこの関数は常に true を返します。

現在のコードでこの split 用ゲートに入るのは、native pack の PCIe probe / 自動調整経路です。CUDA canonical pack の別経路は layer split 時に `pcie_frac_auto` を有効にしません。source の `pcie_auto_split_ok()` 自体には HIP の compile-time guard がなく、native pack の split 経路は HIP 専用の条件式ではありません。一方、`docs/DETAILS.md` はこの変数を HIP の opt-in と説明しています。この資料上の説明とソースの条件式の差を踏まえ、実際に使う場合は backend と pack の組み合わせに注意が必要です。根拠: `src/program/generate.cpp:2863-2895,1622-1626,1630-1638`。

## 実行時の詳細

起動時に H2D PCIe bandwidth を probe し、CPU の native expert pool については基準割合を設定します。layer split で `pcie_frac_auto` が許可されるのはこの自動調整経路です。decode 中は最初の 48 window、その後は 96 window ごとに miss expert 数と CPU pool の処理時間を集計します。miss が 300 件未満なら測定を見送り、2000 window に達すると自動調整を止めます。割合は link speed `L` と CPU pool 速度 `R` から `L / (L + 1.85 × R)` を求め、0.05 刻みに丸めて 0.10..0.60 に制限します。調整回数は最大 3 回です。根拠: `src/program/generate.cpp:1736-1769,8666-8676`。

値が変わったとき stderr に `strata serve: PCIe share: ...` の行を出し、CUDA0 と後段 stage の `pcie_num` を更新します。後段 stage はそれぞれの probe 済み link speed と同じ CPU pool 速度から割合を計算します。更新されない場合はこのログは出ません。根拠: `src/program/generate.cpp:8680-8706,11691-11696`。

各 request で個別の `pcie_frac` tuning 値が起動時割合と異なる場合、その request 中は自動更新を行わず、累積計測の基準を取り直します。`--pipeline-windows` 経路では verdict ごとにも自動調整 step を呼びます。資料には 3 stage 以上の pipeline loop ではこの調整を実行しない条件が記されています。根拠: `src/program/generate.cpp:8680-8685,10663-10697,12459,12736`; `docs/DETAILS.md:1704-1709`。

`docs/DETAILS.md` は、2 枚の R9700 を使った 16 GB-equivalent 条件などで測定値を報告していますが、これは記載された特定条件の結果であり、他の GPU 構成での速度向上を保証するものではありません。出典: `docs/DETAILS.md:1709`。

## 根拠

- 環境変数の parse と static cache: `src/program/generate.cpp:1622-1626`
- HIP 世代判定: `src/program/generate.cpp:1630-1638`
- 起動時 probe と auto 条件: `src/program/generate.cpp:2858-2895`
- 自動調整 eligibility と layer split 初期化: `src/program/generate.cpp:8666-8676`
- 測定・割合計算: `src/program/generate.cpp:1736-1769,8680-8706`
- request 内の割合適用、pipeline / 通常 decode からの呼び出し: `src/program/generate.cpp:10663-10697,11691-11696,12459,12736`
- 説明・測定条件: `docs/DETAILS.md:1698-1709`

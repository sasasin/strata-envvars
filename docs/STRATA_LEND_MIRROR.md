# `STRATA_LEND_MIRROR`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。

## 役割

SYCL の `--stream-experts` 経路で、prompt prefill が一時的に借りる expert-cache の末尾スロットに元々入っていた expert も、起動時に pinned host memory の mirror 候補へ加えます。prefill が借りた領域を返すときの expert 読み戻しに mirror を使えるようにする設定です。GPU に収まらない通常の expert の mirror 候補が先に処理され、借用スロットの expert は追加候補として後ろに並びます。

この変数を読むのは `sycl/src/program/generate.cpp` の起動時 mirror 構築だけです。ほかの backend で同名を読む箇所はありません。

## 値と判定

値は `std::atoll` で `int64_t` に変換されます。文字列全体の検証はありません。先頭の空白と符号は変換規則に従い、数値の後ろにある文字列は無視されます。空文字や数値に変換できない文字列は `0` になり、末尾スロットの追加は行われません。

| 設定 | 候補に追加するスロット |
|---|---|
| 未設定 | キャッシュの `slots / 10` と 1,200 の小さい方 |
| `0`、負数、または数値変換結果が 0 | なし |
| 正数 `N` | キャッシュ末尾の最大 `N` スロット。`N` がスロット数を超える場合は全スロットまで |

たとえば `12junk` は `12` として扱われます。正数の場合、コードは `first_tail = slots - min(N, slots)` を求め、そこ以降のスロットを対象にします。

## 有効になる条件

末尾スロットの候補追加は、次の条件がすべて成立するときだけ行われます。

- `--stream-experts` が指定されている。
- expert source が GGUF source で、expert cache のスロット数が正である。
- prefill が cache を借りる設定である（`--no-prefill-borrow` ではない）。
- `--prefill` の chunk が正である。
- 単一 GPU である（multi-GPU では追加しない）。

設定値が正でも、この条件を満たさなければ無視されます。追加候補は通常の VRAM miss 候補より後ろに並びます。mirror の総容量は別変数 `STRATA_MIRROR_MIB` で制限されるため、容量が足りない場合は末尾スロットの候補に到達する前に打ち切られることがあります。また mirror 容量が 0、候補が空、または pinned memory の確保・読み込みに失敗した場合は、期待する追加 mirror は得られません。

## 実行時の詳細

値は上記条件内で mirror 候補を構築する際に読み取られ、生成開始時の mirror 構築に使われます。関数内 static cache ではありませんが、起動後に環境を変更しても、既に構築した候補や mirror は再評価・再構築されません。

候補列は、まず profile 上の VRAM miss、次に profile に載らない VRAM miss、最後に借用末尾スロットに resident な expert の順です。layer split の場合は通常 miss mirror の対象 layer を最初の split 境界までに制限しますが、末尾スロット候補を追加する条件が `!multi_gpu` なので、この変数による候補追加自体はありません。mirror の容量上限を超えるところで `GgufExpertSource::mirror()` が候補列を打ち切ります。

mirror 構築成功時は stderr に、通常 miss と prompt loan のスロットからそれぞれ何件 mirror したか、合計 GiB と所要秒を含む `strata generate: ... mirrored in pinned host memory ...` のログが出ます。mirror に失敗するとエラー理由と `(they stay on the SSD)` が stderr に出ます。`STRATA_VERIFY_NO_HOST` が設定され、通常の VRAM miss が mirror されなかった場合は生成を拒否する経路もあります。

## 文書・測定値

`docs/INTEL.md` は、B70 の測定条件で prompt loan の末尾 10% の cache slot も mirror する変更に触れ、`STRATA_LEND_MIRROR=0` で無効化できると記しています。そこで報告された複数の prompt/server 実行時間の変化は、その文書に記載の B70・モデル・設定での測定値です。一般的な性能保証ではありません。`docs/DETAILS.md` にはこの変数の個別説明を確認できませんでした。

## 根拠

- `sycl/src/program/generate.cpp:4767-4803` — mirror 候補の目的、通常 miss と借用スロット候補の順序、条件、`STRATA_LEND_MIRROR` の parse と末尾範囲。
- `sycl/src/program/generate.cpp:4812-4825` — mirror 容量の取得、成功・失敗ログ。
- `sycl/src/core/gguf_expert_source.cpp:118-130` — 候補順に容量上限まで取り込む処理。
- `sycl/src/prefill/prefill.cpp:1250-1291` — prompt 借用バッファの relayout 処理。
- `docs/INTEL.md:808-823` — B70 の測定条件と prompt loan 末尾 slot の mirror に関する記述。

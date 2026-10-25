# `STRATA_OWNED_PRICE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリ、テスト、ベンチマーク記録は実装根拠から除外した。

## 役割

自動 expert-cache サイズ計算で、プロンプト（prefill）経路が cache から借りずに自分で確保する GPU バッファの予約量を選ぶ。値が厳密に `exact` のとき、従来の概算式の代わりに `Prefill::bytes_needed_owned(...)` の計算値を使い、MiB 切り上げ後に 64 MiB の余裕を加える。その分は VRAM reserve に足され、expert cache に割り当てられる slot 数が減る。

## 値と判定

環境変数の値は `std::string(v) == "exact"` で文字列全体を比較する。大文字小文字を区別し、空白除去や数値変換はしない。

| 状態 | 結果 |
|---|---|
| 未設定 | 従来式を使う |
| 空文字 | 従来式を使う |
| `exact` | 実バッファ計算値（MiB 切り上げ）+ 64 MiB を使い、その値と従来式の値を stderr に出す |
| `EXACT`、` exact`、`exact `、その他の文字列 | 従来式を使う |

従来式は `160 + (prefill_chunk * 680) / 1024` MiB で、整数演算のため端数は切り捨てられる。`exact` の計算値は `bytes_needed_owned` のバイト数を MiB 単位に切り上げた後、さらに 64 MiB を加える。

## 有効になる条件

環境変数の分岐に到達するのは、次の条件を満たす自動 cache サイズ計算時。

- `--expert-cache auto` などで `o.expert_cache < 0` になっている。expert profile を読み込み、`--expert-cache 0` の場合も自動サイズに変換される。
- `--prefill` の chunk が正の値。
- prompt buffer borrowing が無効。コード上 `pf_borrow = !o.no_prefill_borrow && !o.expert_profile.empty()` なので、典型的には `--no-prefill-borrow` を指定するか、profile を使わない場合。

この guard の外では環境変数は評価されず、予約量への効果もない。手動の `--expert-cache N` では自動計算ブロックに入らない。複数 GPU の layer-split サイズ探索には別の `split_pf_mib` 概算式があり、`STRATA_OWNED_PRICE` はそこでは参照されない。

## 実行時の詳細

CUDA/HIP 側の `src/program/generate.cpp` と SYCL 側の `sycl/src/program/generate.cpp` に同じ環境変数判定がある。自動 cache の予約量を求める関数が、chunk なしまたは borrowing 有効なら 0 を返す。そうでなければ関数内 static の判定値を初回に読み、以後そのプロセスでは再評価しない。したがって、適用される経路で判定が初期化された後にプロセス環境を変えても結果は変わらない。

`exact` の場合、モデル形状・session 状態・chunk、CUDA/HIP 側では source の有無を `Prefill::bytes_needed_owned` に渡す。実装は owned allocation のサイズを 2 MiB granule で数え、ring buffer は一括確保として数える。得た byte 数を MiB に切り上げて 64 MiB を足し、通常 reserve と合算して空き VRAM から cache slot 数を算出する。profile があれば slot 数は profile の件数を上限にする。stderr には次の形式の説明が出る（chunk と MiB 値は実行時計算値）。

```text
strata generate: STRATA_OWNED_PRICE=exact: the prompt path's own buffers for a <chunk>-token chunk: <mib> MiB (the 0.1.39 rule: <legacy_mib> MiB)
```

この変数は prompt buffer の予約計算を変えるもので、prompt の計算内容や出力を直接変更する分岐ではない。予約量の違いは自動 cache の slot 数に反映される。

## 文書との照合

`docs/DETAILS.md` は 0.1.40 の switch として、`STRATA_OWNED_PRICE=exact` が prompt path の own buffers を従来ルールではなく実割り当てで cache sizing に価格付けすると説明している。コードはその説明に沿うが、実計算後に allocator margin として 64 MiB を加える点もある。資料の性能値は本変数の直接効果を示す比較として記載されていないため、ここでは性能向上を主張しない。

## 根拠

- `src/program/generate.cpp:4788-4799` — 従来概算、厳密な文字列比較、実計算、stderr 出力、64 MiB margin。
- `src/program/generate.cpp:4801-4843` — 自動 cache 計算で予約量を合算し、空き VRAM から slot 数を算出。
- `src/program/generate.cpp:4878-4899`、`sycl/src/program/generate.cpp:4324-4345` — profile による borrowing、minimum slot / reserve 調整との関係。
- `sycl/src/program/generate.cpp:3424-3440,4278-4289` — SYCL 側の borrowing 判定、layer-split 用別概算式、同じ環境変数判定。
- `src/prefill/prefill.cpp:1823-1837,1846-1854`、`sycl/src/prefill/prefill.cpp:1855-1869,1906-1910` — owned buffer を 2 MiB granule で数える実装と ring allocation の扱い。
- `docs/DETAILS.md:260-271` — 0.1.40 の switch としての説明。

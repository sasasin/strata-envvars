# `STRATA_SSD_GBPS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

モデルファイルがあるドライブの読み取り速度を GB/s で指定し、host-aware prompt planner が各 chunk/ring 候補の予測時間を計算するときに使う。値は `drive_read_gbps()` が `pp::Host::ssd_gbps` に設定され、planner は予測 file-read bytes をこの速度で割って候補を比較する。chunk/ring の選択が変わることはあるが、重み・expert の内容や生成 token を直接変更する設定ではない（`engine/src/program/generate.cpp:1889-1905,11449-11518`; `engine/include/strata/program/prefill_plan.hpp:81-99,109-127`）。

## 値と判定

`std::getenv` で設定有無を調べ、設定されていれば `std::atof(e) > 0.0` のときだけ採用する。正数として変換できない値はエラーにせず既定値へ進む。`atof` は文字列全体の妥当性を検証しないため、先頭の数値部分が正なら後続文字列があっても採用される。空白や数値の後ろの文字を独自に検査せず、上限 clamp もない。`NaN` は `> 0.0` を満たさず fallback し、正の無限大は条件を満たすため採用される（`engine/src/program/generate.cpp:1891-1905`）。

| 条件 | unset | 有効になる値（例） | 無効になり既定値へ戻る値（例） |
|---|---|---|---|
| 全 platform | platform/drive 判定値 | `0.1`, `1`, `2.5`, ` 1.2`, `1.2junk`, `inf` | 空文字、`0`, `-1`, `true`, `junk`, `NaN` |

未設定時、または変換結果が 0 以下の場合、Linux ではモデルファイルのあるデバイスを `/sys` で調べ、回転ディスクなら `0.15`、NVMe なら `2.5`、その他の非回転ディスクなら SATA-class として `0.45` GB/s を使う。デバイスを判別できない場合は `1.5` GB/s。Windows はデバイス判別を行わず `1.5` GB/s を使う（`engine/src/program/generate.cpp:1840-1858,1889-1905`）。

## 有効になる条件

- Host-aware planner が呼ばれること。通常の単発 `generate` 経路では `--prefill auto`、借用可能な expert cache、`d_res`、`k > 0`、prompt segment が 1024 token より長いことが呼び出し条件（`engine/src/program/generate.cpp:23990-24010`）。
- planner 内で `o.prefill_auto` が真、chunk が正、`srcp == &src`、`STRATA_PREFILL_HOST_PLAN` が `0` で無効化されておらず、`Prefill::ring_bytes_enabled()` が真であること。さらに expert 総量が 0 でなく GPU cache が全 expert を保持していないこと、host memory sampling が成功すること（`engine/src/program/generate.cpp:11432-11447`; `engine/src/prefill/prefill.cpp:833-835,3911-3913`）。
- `--prefill N` のような固定 chunk では `o.prefill_auto` が偽となり、planner は使われない。`STRATA_PREFILL_HOST_PLAN` は先頭文字が `0` のとき無効化する（`generate.cpp:4000-4008,11438-11441`）。`STRATA_RING_BYTES=0` も planner の条件を満たさなくする。`STRATA_PREFILL_RING` は planner が選ぶ ring の実際の解決値に優先するが、`STRATA_SSD_GBPS` の速度値は上書きしない（`engine/src/prefill/prefill.cpp:833-835,843-875`; `engine/include/strata/prefill/prefill.hpp:204-211`）。
- この値を指定する CLI 引数はなく、planner が使われる場合は本変数の正の数値が drive の自動判定値に優先する。

## 実行時の詳細

値は `drive_read_gbps()` の呼び出しごとに環境から読み直され、static cache には保存されない。同関数は host-aware planner の実行条件を通過したときだけ呼ばれる。単発 generate では prompt の chunk 設定中に呼ばれ、`n_batched > 1024` かつ loan が可能な場合に評価される。serve 経路では cache/borrow の初期化中に auto chunk planner から呼ばれる（`engine/src/program/generate.cpp:11432-11453,12449-12459,12629-12657,23990-24010`）。このため serve 中に環境を変更しても、初期化済みの prompt plan は再計算されない。値が効いても planner が元の chunk/ring を維持することがあり、変更は必ず発生するわけではない。planner は候補予測時間が少なくとも 5% かつ 2 秒改善するときだけ変更を採用し、それ未満の差なら既存選択を保つ（`engine/include/strata/program/prefill_plan.hpp:106-127`）。

## ログと測定値

Planner が実行されると stderr に `strata: prefill plan inputs: ... drive %.2f GB/s (%s); ...` を出し、ここに採用速度と理由を表示する。設定値が採用された場合の理由文字列は `STRATA_SSD_GBPS`。planner の選択結果は `strata: prefill plan: ...` として出力され、選択変更時には chunk/ring と予測 read 量・時間、変更なしの場合には `kept` と予測値を表示する。条件未達で planner が早期 return した場合、これらの planner log は出ない（`engine/src/program/generate.cpp:1892-1894,11504-11518`）。この環境変数自体に紐づけて条件を示す実測値は、対象ソースと `docs/DETAILS.md` には記載がない。`DETAILS.md` は drive speed が host-aware plan に用いられ、`STRATA_SSD_GBPS` がその値を override すると説明している（`docs/DETAILS.md:346-351`）。

## 根拠

- `engine/src/program/generate.cpp:1840-1858,1889-1905` — drive 判別、速度の既定値、環境変数の parse。
- `engine/src/program/generate.cpp:11432-11518` — planner 条件、host inputs、ログ、chunk/ring 選択。
- `engine/src/program/generate.cpp:12449-12459,12629-12657` — serve 側の呼び出し条件。
- `engine/src/program/generate.cpp:23990-24025` — generate 側の呼び出し条件。
- `engine/include/strata/program/prefill_plan.hpp:81-99,106-127,152-173` — 予測時間、変更採用条件、ログ文言。
- `engine/src/prefill/prefill.cpp:833-835,843-875,3911-3913` — ring-byte 条件と ring override。
- `docs/DETAILS.md:346-351` — prompt host plan と drive speed override の説明。

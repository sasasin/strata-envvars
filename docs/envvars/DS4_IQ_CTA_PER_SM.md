# `DS4_IQ_CTA_PER_SM`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

DeepSeek V4.1（DS4）のIQ CUDAカーネルが使う、常駐ブロック数の見積もりをSM（Streaming Multiprocessor）あたりで上限設定する開発・測定用フック。カーネルごとにCUDA occupancy APIで得た「SMあたりの最大アクティブブロック数」をこの値で制限し、その結果から永続グリッドのブロック数を決める。GPUのoccupancyを増やす設定ではなく、実測値以下に制限する用途である。

## 値と判定

| 環境変数 | 処理 |
| --- | --- |
| 未設定 | CUDA occupancy APIの値 `per` をそのまま使う。 |
| 設定あり（空文字を含む） | `std::atoi` で整数変換し、最低値を1にしてから `per` との小さい方を使う。空文字や数値に変換できない文字列は `atoi` が0を返すため、下限1として扱う。 |
| 数字の後ろに文字がある | `atoi` の変換規則に従い、先頭の整数部分を使う（例: `2x` は2）。 |
| 0または負数 | `std::max(1, ...)` によって1として扱う。 |

最終的な常駐ブロック上限は `max(1, sms * max(per, 1))`。`DS4_IQ_MAX_SMS` が設定されている場合はSM数 `sms` も同様に最低1へ丸めて上限をかけるため、両変数の積が使われる。

## 有効になる条件

- CUDAビルドのDS4 IQ実装が対象。HIPでは `kPersist` が常に `false` であり、通常のグリッドを使うため、この変数による制限は適用されない。
- `kPersist<T>` が真の型だけが対象で、コードブックのテーブルサイズが8 KiB以上の型に限られる。CUDAのgate/up・downカーネル、および最大4行のlightカーネルが該当する。
- 常駐ブロック数は、当該カーネルが実際に処理するwork item数を超えないようさらに切り詰められる。したがって、work item数がすでに上限以下なら値を変えても起動グリッドは変わらない。

## 実行時の詳細

`resident_ctas<Kernel>()` は現在のCUDA deviceについてSM数を取得し、`cudaOccupancyMaxActiveBlocksPerMultiprocessor` でカーネル固有のoccupancyを得る。その初回計算時に環境変数を読み、結果をカーネル特殊化ごとのdevice別静的キャッシュ（16 device分）へ保存する。以後の呼び出しではキャッシュ値を返すため、プロセス起動後に環境変数を変更しても、すでに計算済みのdevice・カーネルには反映されない。

gate/up・downでは `min(groups * tiles, resident_ctas)` 個のブロックで起動し、各ブロックが複数のrow tileを順番に処理する永続グリッドとなる。lightカーネルは `max_rows <= 4` の経路で同じ上限を使う。より多い行数のlight処理や非永続型は通常グリッドで起動する。変数値を出すログや警告はこの箇所にはない。

## 根拠

- `src/dsv41/ds4_iq.cu:518-526` — 永続グリッドの条件。HIPでは無効、CUDAではテーブルサイズ8 KiB以上。
- `src/dsv41/ds4_iq.cu:1118-1140` — HIP/CUDA別処理、SM数・occupancy取得、環境変数の `atoi` と下限処理、device別キャッシュ。
- `src/dsv41/ds4_iq.cu:1142-1161` — 永続グリッドのwork item数上限とgate/up・downの起動。
- `src/dsv41/ds4_iq.cu:1229-1240` — lightカーネルでは最大4行の経路のみ常駐グリッドを使う。
- `docs/DETAILS.md` にこの変数の追加説明や測定値は見当たらなかった。

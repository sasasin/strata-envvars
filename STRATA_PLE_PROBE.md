# `STRATA_PLE_PROBE`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

PLE（ngram）テーブルを `--ple-io direct` で開いた直後に行う、ランダム行読み取り速度の起動時 probe を抑止します。名前に `PROBE` とありますが、実装上はこの変数を設定すると probe は実行されません。probe を強制する用途ではありません。

## 値と判定

値の内容は parse されず、`std::getenv("STRATA_PLE_PROBE") != nullptr` かどうかだけを見ます。

| 状態 | 動作 |
|---|---|
| 未設定 | `--ple-io direct` の場合に probe を実行 |
| 任意の値を設定 | probe をスキップ。`1`、`0`、その他の文字列で差はない |
| 空文字を設定 | probe をスキップ（環境変数は存在するため） |

## 有効になる条件

変数が未設定で、PLE テーブルが指定されて正常に開かれ、I/O mode が `Direct` の場合だけ probe に進みます。`--ple-io` の既定値は `direct` です。`--ple-io mmap` または `--ple-io ram` ではこの probe 分岐に入りません。PLE テーブルを使わない場合も読み取り箇所へ到達しません。

CUDA/HIP を使う `src/program/generate.cpp` と SYCL の `sycl/src/program/generate.cpp` に同じ判定があります。両方とも環境変数が設定済みなら mode に関係なく値を使わず、probe だけでなく probe 内の遅い読み取りに対する警告や自動切替判定も飛ばします。ほかの PLE 読み取りやテーブル mode 自体はこの変数で変更されません。

## 実行時の詳細

テーブルを開いた後、未設定なら `ple_direct_rows_per_s()` が最大64 batch（batch あたり64行）でランダム行を読み、経過が約0.6秒を超えた時点で止めて rows/s を計算します。テーブルが4096行未満、読み取り失敗など、測定できない場合は非正の値を返します。測定値が15,000 rows/s以上なら `PLE direct read probe: ... (fine)` を stderr に出します。0より大きく15,000未満なら、通常は低速警告を出します。加えて `STRATA_PLE_AUTO_MMAP` が非ゼロとして parse され、かつ `--ple-io` が明示指定されていない場合には、テーブルを mmap mode で開き直します。これらはすべて `STRATA_PLE_PROBE` が未設定のときだけ起きます。

`STRATA_PLE_PROBE` はテーブルを開いた後の起動処理で直接読み取られ、結果を static cache しません。この箇所の判定後に環境を変更しても、その起動中の probe の実施・抑止は変わりません。コード上、子プロセスへの転送・上書きは確認できません。

## 根拠

- `src/program/generate.cpp:387` — `--ple-io` の既定値は `direct`。
- `src/program/generate.cpp:3187-3214,3217-3244` — PLE table を開いた後の env 判定、probe、閾値、ログと `STRATA_PLE_AUTO_MMAP` による切替。
- `src/program/generate.cpp:1743-1765` — probe がランダム行 batch を読み、最大約0.6秒測定する処理。
- `sycl/src/program/generate.cpp:460,3004-3031,3034-3061` — SYCL 側の既定値と同じ env 判定・probe 分岐。
- `sycl/src/program/generate.cpp:1631-1653` — SYCL 側 probe 実装。
- `docs/DETAILS.md:1868-1870` — direct I/O が既定であること、起動 probe が15K rows/s未満で警告すること、および `STRATA_PLE_AUTO_MMAP` による切替の説明。`STRATA_PLE_PROBE` 自体の説明はありません。

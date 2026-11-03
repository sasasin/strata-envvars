# `STRATA_DF2_RING_STATS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DFlash2 の serve request 開始時に、ring log の再構築状況を stderr へ出す診断スイッチです。ring の再構築や内部カウンタの更新を有効化する変数ではありません。統計の集計はこの変数の有無にかかわらず行われ、変数が制御するのはログ出力です（`src/core/dflash2.cpp:942-951`、`sycl/src/core/dflash2.cpp:676-686`）。

## 値と判定

値の文字列や数値は parse されません。`std::getenv(...) != nullptr` で設定有無だけを見ます。

| 設定 | 判定 |
|---|---|
| unset | 詳細な ring 統計行を出さない |
| 空文字を含む任意の設定値 | 有効。`0`、`false`、空文字も設定されていれば有効 |

大文字小文字、空白、数値としての妥当性は検査されません。CLI 引数や設定ファイルによる上書き・優先順位はありません。この変数は既存処理へ診断出力を追加します。

## 有効になる条件

- DFlash2 実装を含む backend で使われる必要があります。完全一致参照は CUDA/HIP 共通の `src/core/dflash2.cpp` と SYCL の `sycl/src/core/dflash2.cpp` にあります。Metal の実装 `metal/src/engine/dflash2.inc` にはこの変数の読み取りがなく、この診断出力はありません。
- `--draft dflash2` で DFlash2 が選択され、読み込み・初期化に成功して serve の request 処理が `begin_request()` に到達する必要があります。各 serve 経路で `use_df2` のときだけ `begin_request()` を呼びます（`src/program/generate.cpp:6765-6775,16032-16046`; `sycl/src/program/generate.cpp:4423-4434,10614-10626`）。DFlash2 が起動しない経路では出力されません。
- ring log が有効である必要があります。`STRATA_DF2_RING_LOG` の値が `0` で始まる場合は log が無効となり、`begin_request()` は統計行の判定より前に戻ります。CUDA/HIP では pinned staging、SYCL では host staging の確保に失敗した場合も log を無効にして stderr に警告を出します（`src/core/dflash2.cpp:746-758,894-900`; `sycl/src/core/dflash2.cpp:214-224,613-634`）。

## 実行時の詳細

CUDA/HIP と SYCL の `begin_request()` は、ring-log 経路で request ごとの集計行を stderr に出すかを `static const bool verbose` に保存します。値はそのプロセスで初めて log 有効の `begin_request()` がこの判定に到達した時点で読み取られ、以降の request では再評価されません。従って、その後にプロセス環境を変更しても集計行の有無は変わりません（`src/core/dflash2.cpp:878-900,942-946`; `sycl/src/core/dflash2.cpp:613-634,676-680`）。

有効なら、各 request の番号、resume と prompt 長、live/parked log の容量、再構築行数・欠落行数、所要時間、parked lineage の復帰有無を含む `strata dflash2 ring: request ...` 行を stderr に出します。これは `begin_request()` が完了したときの行です。ring rebuild が失敗した場合の `strata dflash2: ...: the ring starts over for this request` などのエラー処理は別に実行され、この変数の有無で変わりません（`src/core/dflash2.cpp:931-946`; `sycl/src/core/dflash2.cpp:665-680`）。

rebuild 中、過去に記録されていない位置についても、設定されていれば rebuild ごとに最大 8 件まで `strata dflash2 ring: position ... was never logged ...` を stderr に出します。この箇所は `getenv()` を都度呼び、集計行の `static` 判定とは異なります（`src/core/dflash2.cpp:815-824`; `sycl/src/core/dflash2.cpp:565-575`）。ring log がオフなら rebuild 自体に進まないため、この警告も出ません。

## 根拠

- 変数の全読み取り箇所（値を parse せず設定有無を判定）: `src/core/dflash2.cpp:823,942`; `sycl/src/core/dflash2.cpp:573,676`。
- serve での DFlash2 起動条件と request ごとの呼び出し: `src/program/generate.cpp:6765-6775,16032-16046`; `sycl/src/program/generate.cpp:4423-4434,10614-10626`。
- ring log 無効時の早期 return および staging 確保失敗: `src/core/dflash2.cpp:746-758,894-900`; `sycl/src/core/dflash2.cpp:214-224,613-634`。
- Metal の `begin_request()` は lineage/ring 状態を扱いますが、この環境変数を読み取らず、該当する統計行も出しません: `metal/src/engine/dflash2.inc:1114-1137`。

候補一覧 `docs/envvars/000_envvers.md` の名前は、CUDA/HIP と SYCL の Strata 所有ソースで値を読む実装が確認できたため、実在する環境変数です。

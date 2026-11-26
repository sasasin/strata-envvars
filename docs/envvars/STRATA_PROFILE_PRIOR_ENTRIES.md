# `STRATA_PROFILE_PRIOR_ENTRIES`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL エンジンが `--expert-profile-save` で学習済み expert profile を保存するとき、読み込んだ profile の順位をどれだけ事前カウントとして残すかを指定する。起動時に読み込んだ profile の順位ごとに指数減衰する重みをルーティング実績へ足し、保存する順位を決める。通常の実績だけで順位付けする処理や、実行中の GPU キャッシュ配置を直接変更しない。読み取り箇所は SYCL 版 `save_profile` の device-count 分岐だけである（`engine/sycl/src/program/generate.cpp:9343-9376`）。

このコードは通常の CUDA/HIP エンジンではなく、Linux x86_64 向けの別プロジェクト SYCL エンジンにある（`engine/sycl/CMakeLists.txt:253-256`）。トップレベルでは `STRATA_ENABLE_SYCL` が既定 OFF で、ON のとき CUDA/HIP と併用できず `sycl/` を追加する（`engine/CMakeLists.txt:23-32`）。SYCL の `strata` 実行ファイルは `generate.cpp` を含む（`engine/sycl/CMakeLists.txt:375-377`）。

## 値と判定

`save_profile` が呼ばれるたびに `std::getenv` で取得する。未設定なら `800000.0` routed entries を使う。設定時は `std::atof` の結果を `std::max(0.0, value)` に渡す。全体文字列の厳密な検証やエラー報告はなく、数値として読めない文字列は通常 0 になり、数値の後ろにある文字は `atof` が消費しない。空文字も 0 として扱われる。負値は 0 に clamp される。たとえば `12.5` は 12.5、`0`・空文字・`abc`・`-1` は 0、`12tail` は数値 prefix の 12 として扱われる。先頭の空白と符号は数値変換に従い受け付ける。真偽値の単語を照合する処理はない。`atof` を使うため、整数限定や小数桁の制限はない。`NaN` などの非有限値について個別の検査・エラー処理はない（`engine/sycl/src/program/generate.cpp:9354-9359`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---:|---|---|
| SYCL の device-count 保存分岐 | 800000.0 | 0 より大きく `atof` で読める数値（例 `1`, `12.5`, `12tail`） | 0 以下、空文字、数値 prefix のない文字列（例 `0`, `-1`, ``, `abc`）は prior 加算量 0 |

## 有効になる条件

- SYCL バックエンドの `strata` を実行していること。CUDA/HIP 側の `engine/src/program/generate.cpp` にはこの名前の読み取りがない。
- `--serve` 経路で `--expert-profile-save PATH` を指定し、終了時または周期保存時に `save_profile` が呼ばれること。周期は `--expert-profile-save-every`（既定 10 分、0 以下なら周期保存なし）で制御され、終了時の保存呼び出しは別にある（`engine/sycl/src/program/generate.cpp:605-609,2175-2178,10285-10289,13283`）。
- `usage_dev_srv` が確保されること。これは `mirror_table_d` があり、かつ保存先が指定されている場合に作られる（`engine/sycl/src/program/generate.cpp:7685-7693`）。`mirror_table_d` は `--stream-experts`、GGUF ソース、VRAM expert cache があり、VRAM 外の expert の mirror が作成できた経路で設定される（`engine/sycl/src/program/generate.cpp:5426-5435,5486-5505`）。この条件がなければ `save_profile` は device-count 分岐を通らず、この変数を読み取らない。
- prior を実際に足すには、`profile_loaded` に順位があることも必要。これは保存先が指定されたとき、読み込まれた `profile` のコピーとして用意される（`engine/sycl/src/program/generate.cpp:3825-3828`）。空なら加算ループは 0 回で、この変数による順位 prior は生じない（`engine/sycl/src/program/generate.cpp:9361-9365`）。

## 実行時の詳細

device-count 分岐では、まず `usage_dev_srv` のカウントをホストへコピーして合計を計算する。各 profile 順位 `r` の expert について `x = r / n`、`n = 層数 × expert 数` とし、`prior_entries * 2 * exp(-2*x) / (1-exp(-2)) / n` をその expert の実績へ加える。続いて `rank_learned_profile` が実績の大きい順に並べ、同点では読み込んだ prior 順位、さらに pair index の順で安定した tie-break を行い、`write_expert_profile` が保存先へ書く（`engine/sycl/src/program/generate.cpp:9350-9370`; `engine/src/core/expert_cache.cpp:246-272`）。従ってこの値が変えるのは保存 profile の順位であり、現在の実行中に使うキャッシュや生成 token ではない。

環境値は `save_profile` 内で保存のたびに再取得し、static cache には保存しない。周期保存は次のリクエストを処理する前に条件を確認し、終了時にも保存を試みる（`engine/sycl/src/program/generate.cpp:10285-10289,13283`）。CLI の `--expert-profile-save-every` は周期条件だけを変え、prior 値を上書きしない。未設定時の 800000 は環境変数の既定値であり、別の CLI 引数による prior 値の指定はない（`engine/sycl/src/program/generate.cpp:9356-9358`）。

## ログと測定値

この変数専用のログや無効値警告はない。保存成功時は `strata serve: expert profile saved to %s (%s, %.0f routed entries counted on the device)`、失敗時は `strata serve: the expert profile was not saved: %s` を stderr に出す（`engine/sycl/src/program/generate.cpp:9370-9374`）。この変数について再現条件を伴う測定値は、確認したソースと `docs/DETAILS.md` には記載がない。

## 根拠

- `engine/sycl/src/program/generate.cpp:9343-9376` — device usage を用いた保存分岐、既定値・読み取り・prior 加算・成功／失敗ログ。
- `engine/sycl/src/program/generate.cpp:3825-3828,7685-7693,8761-8771` — 読み込んだ順位の保存、device counter の確保と profile 保存準備。
- `engine/sycl/src/program/generate.cpp:5426-5505` — stream expert と mirror table の作成条件。
- `engine/sycl/src/program/generate.cpp:10285-10289,13283` — 周期保存と終了時保存。
- `engine/src/core/expert_cache.cpp:246-272` — 学習済み順位のソートと tie-break。
- `engine/CMakeLists.txt:23-32`; `engine/sycl/CMakeLists.txt:375-377` — SYCL が別 backend であり、対象ファイルが SYCL 実行ファイルに含まれること。

# `STRATA_ROCM_INDEX`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の Strata 作業ツリーは `## main...origin/main` で、未コミット変更はありません。

## 役割

Strata のセットアップ時に、AMD ROCm Python wheel を取得する package index URL を差し替えます。Linux では HIP engine 用 ROCm を AMD TheRock の wheel から `.venv` に導入するときに使い、Windows では `tools/hip/build_windows.bat` が専用 ROCm venv に `rocm[...]` を入れるときに使います。実行中の Strata engine / server が読む環境変数ではありません。

## 値と判定

| 経路 | 未設定・空文字 | 非空の設定値 | 検証・変換 |
|---|---|---|---|
| Linux `setup.py` | GPU architecture に対応する `ROCM_INDEXES[arch]` を使う | 値を index URL としてそのまま使う | trim、URL 検証、末尾 `/` の正規化はしない |
| Windows HIP build batch | batch 内で `https://nightly.repo.amd.com/rocm/whl-next/` を設定 | その値を `pip --index-url` に渡す | batch 側で URL 検証や正規化はしない |

Linux の Python は `os.environ.get(...) or ...` なので、未設定と空文字はどちらも既定 index に fallback します。空白だけの文字列など、truthy な非空値はそのまま採用されます。architecture の標準 index は gfx1100/1101/1102 が `gfx110X-dgpu`、gfx1200/1201 が `gfx120X-all`、gfx1030/1031 が `gfx103X-all`、gfx1151 が専用 index です。gfx1103/gfx1150 はそれぞれ実験用 opt-in が有効なときだけ architecture 候補に加わります（`setup.py:3643-3652,3668-3676`）。

Windows batch は `if not defined STRATA_ROCM_INDEX` で既定値を設定します。Windows の環境変数が未定義または空なら既定 URL になり、値がある場合はそのまま pip 引数になります（`tools/hip/build_windows.bat:18-19,24-29,47-50`）。

この変数自体に数値境界・無効値 fallback はありません。Linux では index URL の `/rocm/` ページから wheel version の一覧を取得し、同じ family の推奨 ROCm version を選びますが、これは index の応答内容に対する version 選択です。HTTP 取得が `OSError` / `ValueError` で失敗すると一覧を空として扱い、推奨 version を維持して pip に進みます（`setup.py:3731-3751,3754-3773`）。別環境変数 `STRATA_ROCM_VERSION` に truthy な値があれば version はその値で固定されますが、index は引き続き `STRATA_ROCM_INDEX` の選択結果です（`setup.py:3662-3664,3754-3768`）。

## 有効になる条件

- Linux のセットアップが HIP backend を選び、`rocm_root()` が呼ばれること。CLI には `STRATA_ROCM_INDEX` の代替オプションはありません。`--backend hip` は HIP backend を選びます（`setup.py:4690-4707,9207-9210`）。
- `ROCM_PATH`（なければ `/opt/rocm`）に `bin/hipcc` と `libhipblas` があり、ROCm version が 7.0 以上（または version header がなく）、HIP 開発ファイルも揃っている場合は、その system ROCm が使われ、index は参照されません。system ROCm が古いか開発ファイル不足なら警告を出して wheel経路へ進みます（`setup.py:4695-4707`）。
- wheel 経路では選択した全 GPU architecture に対して `rocm_index(arch)` を呼びます。同じ家族の index にまとまらない複数 GPU は、system ROCm を使えない限り `fail(...)` で停止します（`setup.py:4707-4711`）。index 変更後にどの wheel を再導入するかは保存 stamp の index/version と比較されます。index/version が一致し、必要条件を満たす場合はインストールをスキップします（`setup.py:4712-4728`）。
- Windows のこの読み取りは、通常の setup の実行経路ではなく `tools/hip/build_windows.bat` を使った HIP engine のビルド・パッケージ作成時です。stamp の内容が要求 version/extras と一致する場合、または `STRATA_ROCM_KEEP=1` の場合は pip install ブロックを通らず、index は pip に渡りません（`tools/hip/build_windows.bat:41-51`）。

## 実行時の詳細

Linux では `rocm_index(arch)` が各 arch の都度環境を読み、同じ index 群を deduplicate した後に 2 種以上なら失敗します。単一 index の場合、保存済み `.strata-rocm.json` に同じ index と version があり ROCm SDK が存在して version override もないと、既定 version の再確認・pip install を省略します。それ以外は `rocm_wanted(index)` が index の `/rocm/` 一覧から version を選び、必要なら `warn(...)` を出し、`pip install --index-url <index>` を実行して stamp に version と index を保存します。pip 実行の失敗は `run(...)` の失敗経路へ伝わります。後続で `rocm-sdk path --root` から得た ROCm root に compiler がなければ `fail(...)` します（`setup.py:3716-3717,3754-3773,4690-4738`）。

Windows batch では、stamp が要求内容と異なり `STRATA_ROCM_KEEP` が `1` でないとき、設定 index を `pip install --index-url` に渡します。pip が失敗すると `|| exit /b 1` で batch が終了します。成功時は `rocm-sdk init` を実行し、さらに失敗すれば同様に終了します（`tools/hip/build_windows.bat:41-53`）。

設定値を Strata engine や子プロセスへ転送するコードは確認できません。ここでの効果はセットアップ時の wheel 取得先に限られます。`docs/AMD_HIP.md:112-116` は Linux の family index と `STRATA_ROCM_INDEX` による override を説明しています。Windows batch の既定値は同文書の Linux family index とは別の URL です。

## 根拠

- `setup.py:3716-3717`: index override の唯一の Python 読み取り箇所。
- `setup.py:4690-4738`: system ROCm 優先、arch ごとの index 選択、複数 family の失敗、stamp 判定、pip への渡し方。
- `setup.py:3731-3773`: index listing と version の選択・警告。
- `setup.py:4809-4827,4880-4899,5032-5037`: HIP engine / HIP vision / image generator のセットアップから `rocm_root()` を呼ぶ経路。
- `tools/hip/build_windows.bat:18-19,24-29,41-53`: Windows の既定値、pip install 条件と終了経路。
- `docs/AMD_HIP.md:112-116`: Linux index family と override に関する説明。

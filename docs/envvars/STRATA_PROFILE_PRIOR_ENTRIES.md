# `STRATA_PROFILE_PRIOR_ENTRIES`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

SYCL 版 `strata serve` が保存する learned expert profile のうち、デバイス上で数えたルーティング回数へ、起動時に読み込んだ expert profile の順位情報をどれだけ加算するかを指定します。通常の CUDA/HIP 実装にはこの名前の参照がなく、調査対象 HEAD では SYCL の `sycl/src/program/generate.cpp` にある1箇所だけで読み取られます。

## 値と判定

| 状態 | `prior_entries` |
|---|---:|
| 未設定 | `800000.0` |
| 設定あり | `max(0.0, std::atof(値))` |

文字列全体の厳密な検証はありません。`std::atof` による数値変換なので、空文字や数値として読めない文字列は通常 `0` になり、数値の後ろに文字が続く場合は数値として読める先頭部分が使われます。負数は 0 に切り上げられ、上限は設けられていません。たとえば `-5` は 0、`12tail` は 12、空文字は 0 です。大文字小文字や真偽値文字列の判定はありません。

## 有効になる条件

この値は、`--expert-profile-save` が指定され、保存時に `usage_dev_srv != nullptr` となる経路でのみ使われます。このデバイス集計領域は `mirror_table_d` が存在するときに割り当てられます。ソース上、mirror table は `--stream-experts`、GGUF source、正の expert cache、かつ実際に expert を pinned host memory へ mirror できた経路で作られます。`STRATA_VERIFY_NO_HOST` でも使われる device-plan の集計経路ですが、この環境変数自体に `STRATA_VERIFY_NO_HOST` の値を調べる条件はありません。通常のホスト側 `heat` を使う保存経路では、この環境変数は参照されません。

## 実行時の詳細

`save_profile()` はサーバーの終了時、および `--expert-profile-save-every` の間隔に達したリクエスト間で呼ばれます。環境変数はこの関数の実行ごとに読み直され、static cache されません。デバイスの routing count を読み出した後、各 expert の基礎値に count を入れ、読み込んだ profile の順位 `r` に対して次の重みを加えます。

```text
prior_entries * 2 * exp(-2 * r / n) / (1 - exp(-2)) / n
```

ここで `n = n_layers * n_expert` です。その後 `rank_learned_profile()` が加算後の値の降順で並べ、同値なら読み込み profile の順位、さらに同値なら pair の index で順序を決めます。このため値を大きくすると、起動時 profile の先頭側へ指数分布の prior mass を強く与え、起動後の routing count と合わせた保存順位に影響します。`0` なら加算はありません。起動時 profile が空なら prior の加算対象もありません。

保存に成功すると stderr に `strata serve: expert profile saved to ...`、失敗すると `strata serve: the expert profile was not saved: ...` が出ます。保存後の profile は次回起動時の expert 配置に使える形式で書かれます。`docs/DETAILS.md` は learned profile の保存タイミングと、Battlemage の `STRATA_VERIFY_NO_HOST` で device-side routing counts から順位を作る経路を説明していますが、この環境変数の既定値や重み式は記載していません。

## 根拠

- `sycl/src/program/generate.cpp:8441-8470` — 保存関数、デバイス count の読出し、既定値 `800000.0`、環境変数の変換、順位重みの加算、成功・失敗ログ。
- `sycl/src/program/generate.cpp:3481-3482` — `--expert-profile-save` が指定された場合に、読み込んだ profile 順を保持。
- `sycl/src/program/generate.cpp:7105-7113,7890-7900` — device count 領域の割当条件と保存用 count の準備。
- `sycl/src/program/generate.cpp:9300-9304,11815` — 定期保存と終了時保存。
- `sycl/src/core/expert_cache.cpp:210-236` — learned profile の並べ替えと同順位時の tie-break。
- `docs/DETAILS.md:605-615` — learned profile の保存・再利用、および SYCL の device-side routing count 経路。環境変数自体の説明はなし。

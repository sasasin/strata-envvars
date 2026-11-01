# `STRATA_EXPERT_NIBBLE_RECHECK`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

4-bit expert slot 機能（`STRATA_EXPERT_NIBBLE`）でロード時に記録した各 VRAM slot の hash を、サーバーの各正常終了リクエスト後に再計算して照合するデバッグ用チェックです。この変数だけでは 4-bit slot を有効にしません。変換対象 slot が実際に構成されていなければ、リクエスト後のチェックも行いません。

## 値と判定

`std::strcmp(rc, "1") == 0` の完全一致だけが有効です。数値変換や真偽値 parse はありません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| `1` | 有効 |
| `0`、`true`、`01`、`1 `、その他の文字列 | 無効 |

既定値は無効です。この変数を上書きする CLI 引数や、別の環境変数からの fallback はありません。`nib::config()` 内の `static const Config` が初回呼び出し時に環境を読み、以後はその値を返すため、プロセス起動後の環境変更は反映されません。

## 有効になる条件

値が `1` でも、次の条件がそろった場合だけチェックされます。

- `STRATA_EXPERT_NIBBLE=1` が有効で、起動時の検査を通り、モデルに変換対象 layer があって、4-bit slot が構成されていること。
- 実行経路が `generate.cpp` のサーバーリクエスト処理であること。
- リクエストがキャンセルされていないこと。

4-bit slot のカーネルは CUDA の `STRATA_EXPERIMENTAL_SM60` ビルドに限られます。HIP・Metal、およびこの macro のない CUDA build では同機能の cache 実装は no-op で、起動検査も通常 slot に戻す経路です。macro が有効でも、実行時 GPU は compute capability 6.0（GP100）であることが要求されます。その他の起動条件により `STRATA_EXPERT_NIBBLE` が無効化された場合も `nib::any_on()` が偽となり、本変数による再検査は実行されません。

## 実行時の詳細

`config()` は `generate.cpp` の起動時設定処理で呼ばれ、再検査値を含む設定を一度だけ作ります。4-bit slot の初期ロードでは各 slot の基準 hash を記録します。リクエストが完了すると、`nib_x` と各 layer-split stage の cache に対して slot hash を再計算し、基準値と比較します。hash は slot の `hashed` bytes（4-bit gate/up 領域と down rows）を対象にし、末尾の未使用 alignment padding は含めません。

照合に成功すると stderr に `strata serve: STRATA_EXPERT_NIBBLE_RECHECK: <件数> 4-bit slots hash as at load (<ms> ms)` を出します。slot の hash 不一致時は詳細を同じ prefix で stderr に出し、続けて `nib::fatal()` が layer / format と `a slot changed after the load` を含む `strata: STRATA_EXPERT_NIBBLE: ... - stopping` を出して `abort()` します。GPU hash の起動・同期・readback が失敗し layer を特定できない場合も、エラーを stderr に出して `abort()` します。

## 根拠

- `include/strata/core/expert_nibble.hpp:238-270`: config の static cache と環境変数の読み取り。対象値は完全一致の `"1"` のみ。
- `include/strata/core/expert_nibble.hpp:190-207`: hash 対象と host 側の hash 定義。
- `include/strata/core/expert_nibble.hpp:33-38,396-400`: 4-bit kernel の build 条件と fatal 時の stderr / abort。
- `src/program/generate.cpp:2666-2690,2692-2705`: 非対応 build の cache stub と CUDA / compute capability 条件。
- `src/program/generate.cpp:4159-4199`: 起動時の `STRATA_EXPERT_NIBBLE` 判定、変換が拒否された時の警告と通常 slot への復帰、再検査が各 request 後に行われる旨の有効ログ。
- `src/program/generate.cpp:7284-7314,7356-7371,7458-7474`: 起動時に変換 slot を作り、hash を記録する cache のロード経路（主 cache と stage cache）。
- `src/program/generate.cpp:2632-2663,17196-17215`: hash の再計算・比較、非キャンセル request の条件、成功ログと失敗経路。
- `CMakeLists.txt:236,251-261,280-284,418-420`: experimental macro の CUDA build 設定。
- `docs/OLDER_GPUS.md:230-236`: `STRATA_EXPERT_NIBBLE_RECHECK=1` を各 request 後に全 4-bit slot を hash する debug switch と説明。上記のコードと一致します。

# `SYCL_UR_USE_LEVEL_ZERO_V2`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

Strata の SYCL 実装はこの変数を、prompt の専門家データ転送に使う専用 copy-engine queue を作るかどうかの判定に読み取る。変数が設定されていて先頭文字が `0` の場合、Strata は専用 queue を作らず、呼び出し元が通常の in-order queue を使う経路に進む。Strata 自身がこの変数を書き換えたり、Level Zero adapter の選択を設定したりするコードは見つからなかった。

## 値と判定

| 環境変数の状態 | Strata の判定 |
| --- | --- |
| 未設定 | この変数による無効化なし。ほかの適用条件を満たせば専用 queue の作成を試みる。 |
| 空文字 | `v[0]` が `\0` なので無効化しない。 |
| 先頭文字が `0`（例: `0`, `0abc`） | 専用 queue 作成を試みず `nullptr` を返す。 |
| その他（例: `1`, `false`, `abc`） | この変数による無効化なし。数値変換、文字列全体の比較、後続文字の検査はしない。 |

判定は大文字小文字を区別する文字列 parse ではなく、最初の1バイトが文字 `0` かどうかだけである。負数や不正値に特別な扱いはない。

## 有効になる条件

この判定が到達可能なのは、SYCL ビルドに Level Zero API header があり、`make_copy_engine_queue()` が専用 queue の作成を試みる場合である。作成にはさらに Level Zero backend が必要で、Battlemage 以外では `STRATA_COPY_ENGINE` の先頭文字が `1` でない限り通常 queue に戻る。`STRATA_COPY_ENGINE` が先頭文字 `0` なら関数は先に終了するため、この変数は読み取られない。

このコードは SYCL 固有の `sycl/src/core/copy_queue.cpp` にあり、呼び出し元は SYCL の prompt prefill における専門家データ転送の初期化である。CUDA/HIP 実装にこの読み取りはない。

## 実行時の詳細

`make_copy_engine_queue()` は、最初に `STRATA_COPY_ENGINE` の無効化判定を行う。Level Zero API がビルドにない場合は通常 queue に戻る。API がある場合、現在 device の queue が既に記録されていればそれを返すため、同一 device での2回目以降はこの変数を再読しない。新しい device について backend と Battlemage/強制有効条件を通過した後、この変数を `getenv` し、先頭文字が `0` なら `nullptr` を返す。

専用 queue が返らなかった場合、prompt の呼び出し元は `dpct::get_current_device().create_queue(true)` で通常 queue を作る。専用 queue の作成が可能な場合は copy-only command queue group 上の immediate command list を SYCL queue として包む。この変数による無効化自体はログを出さない。通常 queue への切替結果として専用 copy-engine の起動ログも出ない。

## 根拠

- `sycl/src/core/copy_queue.cpp:73-79`: 関数入口、`STRATA_COPY_ENGINE` の無効化と Level Zero API 未対応時の return。
- `sycl/src/core/copy_queue.cpp:80-99`: device queue の cache、Level Zero/Battlemage 条件、対象変数の読み取りと先頭文字判定。
- `sycl/src/core/copy_queue.cpp:100-138`: 専用 queue の作成、成功ログ、例外時の通常 queue fallback。
- `sycl/src/prefill/prefill.cpp:987-994`: prompt prefill の専門家コピー queue を要求し、失敗時に通常 in-order queue を作成。
- `sycl/CMakeLists.txt:228,233`: `copy_queue.cpp` と SYCL prefill 実装を SYCL ビルド側へ登録。
- `sycl/include/strata/copy_queue.hpp:10-15`: queue の目的と fallback に関する実装コメント。
- `docs/INTEL.md:812-817`: SYCL copy-engine 経路の説明。adapter についての資料上の説明はここでは参照情報とし、対象変数の現行動作は上記コードの判定に基づく。

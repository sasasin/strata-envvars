# `DS4_NO_PAD`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Metal の DS4 runtime で GPU device allocation と host allocation を作る際、要求サイズを 16 KiB 境界に切り上げる処理を抑止します。設定すると要求サイズのまま `MTL::Device::newBuffer` に渡します。これは allocation size の変更であり、環境変数名から想像できる別の padding 動作は確認できません。

## 値と判定

値を parse せず、`std::getenv("DS4_NO_PAD")` が null かどうかだけを判定します。

| 環境変数 | allocation size |
|---|---|
| 未設定 | 要求サイズ（0 の場合は 1 byte）を 16,384 byte 単位で切り上げ |
| 設定あり | 要求サイズ（0 の場合は 1 byte）のまま |

空文字を含め、値が存在すれば有効です。`0`、`false`、その他の文字列にも違いはありません。数値変換、文字列比較、値域検証、CLI 引数や他の環境変数との優先順位はありません。丸め式に明示的な overflow 検査はありません。

## 有効になる条件

この読み取りは `metal/src/gpu/runtime.cpp` の `STRATA_DS4_RUNTIME` compile macro 下にあります。同 macro が定義されるのは Metal CMake target `ds4_rt_gpu` と `ds4_rt_mm` で、CMake コメントでは DS4 engine がこれらのファイルを独自コピーで使い、Qwen engine の `strata` と他 target では macro が off とされています (`metal/CMakeLists.txt:152-164`)。macro が off の場合、この変数は読まれず、Metal runtime は要求サイズ（0 は 1）を使います (`metal/src/gpu/runtime.cpp:370-377`)。

## 実行時の詳細

device allocation は `malloc_device_raw()`、host allocation は `host_alloc_raw()` から同じ `new_alloc()` を通ります。環境変数は `new_alloc()` の各呼び出しで直接読み取られ、static cache されません。したがって同一プロセス内でも allocation の時点で値が異なれば判定結果が変わります。サイズはその後 `newBuffer()` に渡されます。作成に失敗した場合は `kErrorMemoryAllocation` を返し、thread-local error に保存します。`error_string()` はこのエラーを `out of memory` と表します。ここにこの変数専用のログ出力はありません (`metal/src/gpu/runtime.cpp:370-390,459-470,512-514`)。

## 根拠

- 唯一の直接読み取りとサイズ計算、Metal buffer 作成、失敗経路: `metal/src/gpu/runtime.cpp:370-390`。
- device/host allocation の呼び出し経路: `metal/src/gpu/runtime.cpp:512-514`。
- macro を DS4 Metal runtime target に付ける設定と適用範囲のコメント: `metal/CMakeLists.txt:152-164`。
- 環境変数候補の掲載: `docs/envvars/000_envvers.md` の `DS4_NO_PAD` 項目。候補名は上記のソース参照によって実在を確認しました。
